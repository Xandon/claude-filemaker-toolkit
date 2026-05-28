#!/usr/bin/env python3
"""
fm_paste_html_gen.py
====================

Generate a self-contained HTML page of FileMaker scripts with per-script
Copy-XML buttons that paste straight into Script Workspace (FM 18+).

Two input modes, both feed the same template:

  EXTRACT  — pull existing scripts from an indexed DDR (.db). Uses
             fm_xml_gen.extract_script_xml + fm_ddr_to_clipboard
             internally.

  AUTHOR   — read a JSON spec describing new scripts, resolve every
             named layout / TO / field / script against the DDR, then
             call fm_step_builders to emit clipboard XML.

Either mode can be mixed in a single page; the JS template treats them
the same.

Usage (programmatic):

    from fm_paste_html_gen import generate_paste_html

    generate_paste_html(
        db_path        = "/path/to/Solution.db",
        items          = [("extract", "Script Name"),   # or ("extract", 974)
                          ("spec",   "/path/to/spec.json")],
        output_path    = "/path/to/out.html",
        title          = "My Scripts",
        include_human  = True,
    )

Usage (CLI — though normally driven through fm_manage.py):

    python fm_paste_html_gen.py <db_path> [--script NAME...] [--spec FILE...]
                                          [--title T] [--no-human] [-o OUT]
"""

from __future__ import annotations

import argparse
import io
import json
import os
import sqlite3
import sys
from contextlib import redirect_stdout
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Local imports — work whether running from the plugin scripts/ folder or via
# fm_manage which adds scripts/ to sys.path.
_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

import fm_step_builders as fsb  # noqa: E402
from fm_xml_gen import extract_script_xml  # noqa: E402


# ─────────────────────────────────────────────────────────────────────────────
# Custom exceptions
# ─────────────────────────────────────────────────────────────────────────────
class ResolveError(Exception):
    """Raised when a spec references a name that can't be found in the DDR."""


class SpecError(Exception):
    """Raised on malformed spec JSON."""


# ─────────────────────────────────────────────────────────────────────────────
# DDR lookups
# ─────────────────────────────────────────────────────────────────────────────
class DDRResolver:
    """Looks up FileMaker object IDs from an indexed DDR SQLite database."""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
        self.c = self.conn.cursor()

    def close(self):
        try:
            self.conn.close()
        except Exception:
            pass

    # ── layouts ──────────────────────────────────────────────────────────
    def layout(self, name: str) -> Tuple[str, int]:
        row = self.c.execute(
            "SELECT layout_id, name FROM layouts WHERE name=? COLLATE NOCASE",
            (name,),
        ).fetchone()
        if row:
            return (row["name"], row["layout_id"])
        # Suggest near matches
        cands = self.c.execute(
            "SELECT name FROM layouts WHERE name LIKE ? COLLATE NOCASE LIMIT 6",
            (f"%{name}%",),
        ).fetchall()
        hint = ", ".join(r["name"] for r in cands) or "(no near matches)"
        raise ResolveError(f"Layout '{name}' not found. Did you mean: {hint}")

    # ── fields ───────────────────────────────────────────────────────────
    def field(self, table: str, field: str) -> Tuple[Tuple[str, Optional[int]], Tuple[str, int]]:
        """Resolve (table_occurrence_name, field_name) → builder field ref.

        Lookup strategy:
          1. table is treated first as a base-table name (fields.table_name).
          2. If miss, table is treated as a table occurrence — we follow
             relationships to find the base table, then re-query.
        Returns ((to_name, to_id_or_None), (field_name, field_id)).
        """
        # Step 1: assume table is the base-table name
        row = self.c.execute(
            "SELECT field_id, name, table_name, table_id FROM fields "
            "WHERE table_name=? COLLATE NOCASE AND name=? COLLATE NOCASE",
            (table, field),
        ).fetchone()
        if row:
            # to_id we don't know from the fields table; the clipboard XML
            # only needs table_name + field_id, so passing None is fine.
            return ((row["table_name"], None), (row["name"], row["field_id"]))

        # Step 2: maybe `table` is a TO name — find the base via relationships
        rel = self.c.execute(
            "SELECT left_table_id AS tid, left_table AS tname FROM relationships "
            "WHERE left_table=? COLLATE NOCASE "
            "UNION "
            "SELECT right_table_id, right_table FROM relationships "
            "WHERE right_table=? COLLATE NOCASE LIMIT 1",
            (table, table),
        ).fetchone()
        if rel:
            row = self.c.execute(
                "SELECT field_id, name, table_name FROM fields "
                "WHERE table_id=? AND name=? COLLATE NOCASE",
                (rel["tid"], field),
            ).fetchone()
            if row:
                return ((table, None), (row["name"], row["field_id"]))

        # Suggest
        cands = self.c.execute(
            "SELECT DISTINCT table_name FROM fields WHERE table_name LIKE ? "
            "COLLATE NOCASE LIMIT 6",
            (f"%{table}%",),
        ).fetchall()
        f_cands = self.c.execute(
            "SELECT DISTINCT name FROM fields WHERE name LIKE ? COLLATE NOCASE LIMIT 6",
            (f"%{field}%",),
        ).fetchall()
        t_hint = ", ".join(r["table_name"] for r in cands) or "(none)"
        f_hint = ", ".join(r["name"] for r in f_cands) or "(none)"
        raise ResolveError(
            f"Field '{table}::{field}' not found.\n"
            f"  Tables matching '{table}': {t_hint}\n"
            f"  Fields matching '{field}': {f_hint}"
        )

    # ── scripts ──────────────────────────────────────────────────────────
    def script(self, name: str) -> Tuple[str, int]:
        row = self.c.execute(
            "SELECT script_id, name FROM scripts WHERE name=? COLLATE NOCASE",
            (name,),
        ).fetchone()
        if row:
            return (row["name"], row["script_id"])
        cands = self.c.execute(
            "SELECT name FROM scripts WHERE name LIKE ? COLLATE NOCASE LIMIT 6",
            (f"%{name}%",),
        ).fetchall()
        hint = ", ".join(r["name"] for r in cands) or "(no near matches)"
        raise ResolveError(f"Script '{name}' not found. Did you mean: {hint}")


# ─────────────────────────────────────────────────────────────────────────────
# Step-spec dispatch
# ─────────────────────────────────────────────────────────────────────────────
def _build_step(step: Dict[str, Any], resolver: DDRResolver) -> Tuple[str, str]:
    """Resolve a single spec step → (xml_string, pseudocode_line).

    Pseudocode is a best-effort human-readable equivalent emitted alongside
    each step so the right-hand panel of the HTML shows what the XML does.
    """
    t = step.get("type")
    if not t:
        raise SpecError(f"Step missing 'type': {step!r}")
    en = step.get("enabled", True)
    en_prefix = "" if en else "// [DISABLED] "

    # comment
    if t == "comment":
        text = step.get("text", "")
        if not text:
            return fsb.comment(enabled=en), f"{en_prefix}#"
        return fsb.comment(text, enabled=en), f"{en_prefix}# {text}"

    # flow control
    if t == "if":
        return fsb.if_step(step["calc"]), f"{en_prefix}If [ {step['calc']} ]"
    if t == "else_if":
        return fsb.else_if_step(step["calc"]), f"{en_prefix}Else If [ {step['calc']} ]"
    if t == "else":
        return fsb.else_step(), f"{en_prefix}Else"
    if t == "end_if":
        return fsb.end_if(), f"{en_prefix}End If"
    if t == "loop":
        return fsb.loop(), f"{en_prefix}Loop"
    if t == "end_loop":
        return fsb.end_loop(), f"{en_prefix}End Loop"
    if t == "exit_loop_if":
        return fsb.exit_loop_if(step["calc"]), f"{en_prefix}Exit Loop If [ {step['calc']} ]"
    if t == "exit_script":
        calc = step.get("calc")
        if calc:
            return fsb.exit_script(calc), f"{en_prefix}Exit Script [ Result: {calc} ]"
        return fsb.exit_script(), f"{en_prefix}Exit Script [ ]"
    if t == "halt_script":
        return fsb.halt_script(), f"{en_prefix}Halt Script"

    # vars / fields
    if t == "set_variable":
        rep = str(step.get("rep", "1"))
        rep_str = "" if rep == "1" else f"[{rep}]"
        return (
            fsb.set_variable(step["name"], step["calc"], rep=rep),
            f"{en_prefix}Set Variable [ {step['name']}{rep_str} ; Value: {step['calc']} ]",
        )
    if t == "set_field":
        fref = resolver.field(step["table"], step["field"])
        return (
            fsb.set_field(fref, step["calc"]),
            f"{en_prefix}Set Field [ {step['table']}::{step['field']} ; {step['calc']} ]",
        )
    if t == "set_field_by_name":
        fref = resolver.field(step["table"], step["field"])
        return (
            fsb.set_field_by_name(fref, step["target"]),
            f"{en_prefix}Set Field By Name [ {step['target']} ; {step['table']}::{step['field']} ]",
        )
    if t == "insert_calculated_result":
        fref = resolver.field(step["table"], step["field"])
        return (
            fsb.insert_calculated_result(fref, step["calc"],
                                         select=step.get("select", False)),
            f"{en_prefix}Insert Calculated Result [ {step['table']}::{step['field']} ; {step['calc']} ]",
        )

    # dialogs / error
    if t == "show_dialog":
        return (
            fsb.show_custom_dialog(step["title"], step["message"],
                                   two_buttons=step.get("two_buttons", False)),
            f"{en_prefix}Show Custom Dialog [ {step['title']} ; {step['message']} ]",
        )
    if t == "set_error_capture":
        on = step.get("on", True)
        return fsb.set_error_capture(on=on), f"{en_prefix}Set Error Capture [ {'On' if on else 'Off'} ]"
    if t == "allow_user_abort":
        on = step.get("on", False)
        return fsb.allow_user_abort(on=on), f"{en_prefix}Allow User Abort [ {'On' if on else 'Off'} ]"

    # nav
    if t == "go_to_layout":
        lref = resolver.layout(step["layout"])
        return fsb.go_to_layout(lref), f'{en_prefix}Go to Layout [ "{lref[0]}" ]'
    if t == "go_to_record":
        target = step.get("target", "First")
        return fsb.go_to_record(target), f"{en_prefix}Go to Record/Request/Page [ {target} ]"
    if t == "enter_find_mode":
        pause = step.get("pause", False)
        return (
            fsb.enter_find_mode(pause=pause),
            f"{en_prefix}Enter Find Mode [ Pause: {'On' if pause else 'Off'} ]",
        )
    if t == "perform_find":
        return fsb.perform_find(), f"{en_prefix}Perform Find []"
    if t == "show_all_records":
        return fsb.show_all_records(), f"{en_prefix}Show All Records"
    if t == "enter_browse_mode":
        pause = step.get("pause", False)
        return (
            fsb.enter_browse_mode(pause=pause),
            f"{en_prefix}Enter Browse Mode [ Pause: {'On' if pause else 'Off'} ]",
        )

    # records
    if t == "new_record":
        return fsb.new_record(), f"{en_prefix}New Record/Request"
    if t == "commit_records":
        nd = step.get("no_dialog", True)
        return fsb.commit_records(no_dialog=nd,
                                  skip_validation=step.get("skip_validation", False)), \
               f"{en_prefix}Commit Records/Requests [ With dialog: {'Off' if nd else 'On'} ]"
    if t == "delete_record":
        nd = step.get("no_dialog", True)
        return fsb.delete_record(no_dialog=nd), \
               f"{en_prefix}Delete Record/Request [ With dialog: {'Off' if nd else 'On'} ]"
    if t == "delete_portal_row":
        nd = step.get("no_dialog", True)
        return fsb.delete_portal_row(no_dialog=nd), f"{en_prefix}Delete Portal Row [ ]"

    # windows / repaint
    if t == "new_card_window":
        lref = resolver.layout(step["layout"])
        return (
            fsb.new_card_window(
                name=step["name"], layout=lref,
                height=step.get("height", 700), width=step.get("width", 540),
                top=step.get("top", 80), left=step.get("left", 120),
                close=step.get("close", True), minimize=step.get("minimize", False),
                maximize=step.get("maximize", False), resize=step.get("resize", True),
            ),
            f'{en_prefix}New Window [ Style: Card ; Name: {step["name"]} ; '
            f'Using layout: "{lref[0]}" ; Height: {step.get("height",700)} ; '
            f'Width: {step.get("width",540)} ]',
        )
    if t == "new_window":
        lref = resolver.layout(step["layout"]) if step.get("layout") else None
        return (
            fsb.new_window(
                name=step["name"], layout=lref, style=step.get("style", "Document"),
                height=step.get("height", 600), width=step.get("width", 800),
                top=step.get("top", 40), left=step.get("left", 40),
                close=step.get("close", True), minimize=step.get("minimize", True),
                maximize=step.get("maximize", True), resize=step.get("resize", True),
            ),
            f"{en_prefix}New Window [ Style: {step.get('style','Document')} ; Name: {step['name']} ]",
        )
    if t == "close_window":
        return fsb.close_window_current(), f"{en_prefix}Close Window [ Current Window ]"
    if t == "freeze_window":
        return fsb.freeze_window(), f"{en_prefix}Freeze Window"
    if t == "refresh_window":
        flush = step.get("flush", True)
        return (
            fsb.refresh_window(flush=flush),
            f"{en_prefix}Refresh Window{' [ Flush cached join results ]' if flush else ''}",
        )
    if t == "refresh_object":
        nm = step.get("name")
        return (
            fsb.refresh_object(nm),
            f"{en_prefix}Refresh Object" + (f' [ Object Name: "{nm}" ]' if nm else ""),
        )
    if t == "refresh_portal":
        nm = step.get("name")
        return (
            fsb.refresh_portal(nm),
            f"{en_prefix}Refresh Portal" + (f' [ Object Name: "{nm}" ]' if nm else ""),
        )

    # subscript
    if t == "perform_script":
        sref = resolver.script(step["script"])
        param = step.get("parameter", "")
        return (
            fsb.perform_script(sref, parameter=param),
            f'{en_prefix}Perform Script [ "{sref[0]}"' +
            (f" ; Parameter: {param} ]" if param else " ]"),
        )

    # escape hatch
    if t == "raw_xml":
        if "xml" not in step:
            raise SpecError("raw_xml step requires 'xml' key")
        return fsb.raw_xml(step["xml"]), f"{en_prefix}{step.get('pseudocode', '// raw XML')}"

    raise SpecError(f"Unknown step type: '{t}'")


# ─────────────────────────────────────────────────────────────────────────────
# Build a single authored-script payload from a spec entry
# ─────────────────────────────────────────────────────────────────────────────
def _build_authored_script(script_spec: Dict[str, Any],
                           resolver: DDRResolver) -> Dict[str, Any]:
    if "name" not in script_spec:
        raise SpecError("Script entry missing 'name'")
    if "steps" not in script_spec:
        raise SpecError(f"Script '{script_spec['name']}' has no 'steps'")

    xml_parts: List[str] = []
    human_lines: List[str] = []
    for step in script_spec["steps"]:
        try:
            xml, pseudo = _build_step(step, resolver)
        except (ResolveError, SpecError) as e:
            raise SpecError(
                f"In script '{script_spec['name']}', step {step!r}: {e}"
            ) from e
        xml_parts.append(xml)
        human_lines.append(pseudo)

    full_xml = fsb.wrap(xml_parts)
    human_text = "\n".join(human_lines) + "\n"
    return {
        "name": script_spec["name"],
        "called_from": script_spec.get("called_from", ""),
        "human": human_text,
        "xml": full_xml,
        "step_count": fsb.count_steps(full_xml),
        "mode": "authored",
    }


# ─────────────────────────────────────────────────────────────────────────────
# Build a single extracted-script payload
# ─────────────────────────────────────────────────────────────────────────────
def _build_extracted_script(name_or_id, db_path: str,
                            resolver: DDRResolver) -> Dict[str, Any]:
    """Pull an existing script's XML out of the DDR and produce a pseudocode dump."""
    # extract_script_xml prints to stdout — swallow it.
    buf = io.StringIO()
    with redirect_stdout(buf):
        xml_content = extract_script_xml(db_path, str(name_or_id), output_path=None)
    if not xml_content:
        raise ResolveError(f"Script '{name_or_id}' not found in indexed solution.")

    # Look up the resolved name + step count for the header.
    try:
        sid = int(name_or_id)
        row = resolver.c.execute(
            "SELECT name, step_count FROM scripts WHERE script_id=?", (sid,)
        ).fetchone()
    except (TypeError, ValueError):
        row = resolver.c.execute(
            "SELECT name, step_count FROM scripts WHERE name=? COLLATE NOCASE",
            (name_or_id,),
        ).fetchone()
    name = row["name"] if row else str(name_or_id)
    step_count = row["step_count"] if row else fsb.count_steps(xml_content)

    # Pseudocode from the indexed human_readable column (the parser populated it).
    if row:
        # find script_id (in case we were given the name)
        sid_row = resolver.c.execute(
            "SELECT script_id FROM scripts WHERE name=? COLLATE NOCASE",
            (name,),
        ).fetchone()
        sid = sid_row["script_id"] if sid_row else None
    else:
        sid = None

    human = ""
    if sid is not None:
        lines = resolver.c.execute(
            "SELECT human_readable FROM script_steps WHERE script_id=? "
            "ORDER BY step_index",
            (sid,),
        ).fetchall()
        human = "\n".join((r["human_readable"] or "") for r in lines) + "\n"

    return {
        "name": name,
        "called_from": "(extracted from indexed solution)",
        "human": human,
        "xml": xml_content,
        "step_count": step_count,
        "mode": "extracted",
    }


# ─────────────────────────────────────────────────────────────────────────────
# Main entry point
# ─────────────────────────────────────────────────────────────────────────────
def generate_paste_html(db_path: str,
                        items: List[Tuple[str, Any]],
                        output_path: str,
                        title: Optional[str] = None,
                        include_human: bool = True,
                        template_path: Optional[str] = None,
                        notice_html: Optional[str] = None,
                        extra_pills: Optional[List[str]] = None) -> Path:
    """Build the paste-ready HTML page.

    items: list of (kind, payload) tuples, in display order.
           kind ∈ {"extract", "spec"}
           payload is either a script name/id (extract) or a spec JSON path (spec).
    """
    resolver = DDRResolver(db_path)
    try:
        scripts_payload: List[Dict[str, Any]] = []
        meta = {"pills": list(extra_pills or [])}
        for kind, payload in items:
            if kind == "extract":
                scripts_payload.append(
                    _build_extracted_script(payload, db_path, resolver)
                )
            elif kind == "spec":
                spec = _load_spec(payload)
                if "meta" in spec and not meta.get("title"):
                    meta["title"] = spec["meta"].get("title")
                if "meta" in spec and spec["meta"].get("notes") and not notice_html:
                    # auto-promote spec notes to the notice block
                    notice_html = _escape_for_html(spec["meta"]["notes"])
                for s in spec.get("scripts", []):
                    scripts_payload.append(
                        _build_authored_script(s, resolver)
                    )
            else:
                raise ValueError(f"Unknown item kind: {kind!r}")
    finally:
        resolver.close()

    if title:
        meta["title"] = title
    meta.setdefault("title", "FileMaker Scripts")
    if notice_html:
        meta["notice"] = notice_html

    options = {"include_human": include_human}

    # Load template
    tpl_path = Path(template_path) if template_path else (
        _HERE.parent / "templates" / "paste_template.html"
    )
    if not tpl_path.exists():
        raise FileNotFoundError(f"Template not found: {tpl_path}")
    template = tpl_path.read_text(encoding="utf-8")

    # JSON-encode payloads, defending against `</script>` injection.
    def _json(v):
        s = json.dumps(v, ensure_ascii=False, indent=2)
        return s.replace("</script>", "<\\/script>") \
                .replace("</Script>", "<\\/Script>")

    html_out = (template
                .replace("/*__SCRIPTS_DATA__*/[]", _json(scripts_payload))
                .replace("/*__META__*/{}", _json(meta))
                .replace("/*__OPTIONS__*/{}", _json(options))
                .replace("/*__PAGE_TITLE__*/", ""))

    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html_out, encoding="utf-8")

    return out


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────
def _load_spec(path: str) -> Dict[str, Any]:
    p = Path(path)
    if not p.exists():
        raise SpecError(f"Spec file not found: {path}")
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise SpecError(f"Spec {path} is not valid JSON: {e}") from e


def _escape_for_html(text: str) -> str:
    import html as _h
    return _h.escape(text).replace("\n", "<br>")


# ─────────────────────────────────────────────────────────────────────────────
# CLI (normally driven through fm_manage.py paste-html)
# ─────────────────────────────────────────────────────────────────────────────
def main():
    p = argparse.ArgumentParser(
        description="Build a paste-ready HTML page of FileMaker scripts."
    )
    p.add_argument("db_path", help="Path to the indexed .db for the solution")
    p.add_argument("--script", action="append", default=[],
                   help="Existing script name or id to extract (repeatable)")
    p.add_argument("--spec", action="append", default=[],
                   help="Spec JSON path describing new scripts (repeatable)")
    p.add_argument("--title", help="Page title (defaults to spec.meta.title or generic)")
    p.add_argument("--no-human", action="store_true",
                   help="Suppress the pseudocode panel (XML only)")
    p.add_argument("-o", "--output", required=True, help="Output HTML path")
    args = p.parse_args()

    items: List[Tuple[str, Any]] = []
    for s in args.script:
        items.append(("extract", s))
    for s in args.spec:
        items.append(("spec", s))
    if not items:
        p.error("Provide at least one --script or --spec.")

    try:
        out = generate_paste_html(
            db_path=args.db_path,
            items=items,
            output_path=args.output,
            title=args.title,
            include_human=not args.no_human,
        )
    except (ResolveError, SpecError) as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(2)

    print(f"Wrote: {out}")


if __name__ == "__main__":
    main()
