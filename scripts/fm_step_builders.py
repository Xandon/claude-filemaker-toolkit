#!/usr/bin/env python3
"""
FileMaker clipboard-XML step builders.

Each function returns a single `<Step …>…</Step>` XML string in the format
FileMaker 18+ accepts when pasting into Script Workspace (Cmd-V / Ctrl-V).
No MBS plugin required.

DESIGN
------
- Builders take *already-resolved* IDs. They do NOT touch the DDR.
  Reference resolution (layout name → layout_id, field name → field_id,
  etc.) lives in `fm_paste_html_gen.py` so these helpers stay pure.
- The TO-name + field-id + field-name triple is what FileMaker actually
  uses on paste. The base-table ID is not in the clipboard format.
- Reference tuples are simple: layouts → `(name, id)`, fields →
  `((to_name, to_id), (field_name, field_id))`. The to_id is optional
  (FM resolves by name + field_id), but we pass it through when known
  for safer round-trips.

Lifted and generalised from the picker proof-of-concept
`build_picker_html.py`.
"""

from __future__ import annotations

import html
from typing import Iterable, Optional, Tuple

# ─────────────────────────────────────────────────────────────────────────────
# Reference tuple types (documentation only — Python doesn't enforce)
#   LayoutRef = (layout_name: str, layout_id: int)
#   TORef     = (to_name: str, to_id: int | None)
#   FieldRef  = (TORef, (field_name: str, field_id: int))
#   ScriptRef = (script_name: str, script_id: int)
# ─────────────────────────────────────────────────────────────────────────────

LayoutRef = Tuple[str, int]
TORef = Tuple[str, Optional[int]]
FieldRef = Tuple[TORef, Tuple[str, int]]
ScriptRef = Tuple[str, int]


# ─── Indentation helper ──────────────────────────────────────────────────────
INDENT = "  "


def _e(value) -> str:
    """HTML-escape a value for use inside an XML attribute or text node."""
    if value is None:
        return ""
    return html.escape(str(value), quote=True)


# ─── Comments and flow control ───────────────────────────────────────────────
def comment(text: Optional[str] = None, enabled: bool = True) -> str:
    """`# (comment)` step. Empty text → empty comment line."""
    e = "True" if enabled else "False"
    if not text:
        return f'{INDENT}<Step enable="{e}" id="89" name="# (comment)"/>'
    return (
        f'{INDENT}<Step enable="{e}" id="89" name="# (comment)">\n'
        f'{INDENT}    <Text>{_e(text)}</Text>\n'
        f'{INDENT}</Step>'
    )


def if_step(calc: str) -> str:
    return (
        f'{INDENT}<Step enable="True" id="68" name="If">\n'
        f'{INDENT}    <Calculation><![CDATA[{calc}]]></Calculation>\n'
        f'{INDENT}</Step>'
    )


def else_if_step(calc: str) -> str:
    return (
        f'{INDENT}<Step enable="True" id="125" name="Else If">\n'
        f'{INDENT}    <Calculation><![CDATA[{calc}]]></Calculation>\n'
        f'{INDENT}</Step>'
    )


def else_step() -> str:
    return f'{INDENT}<Step enable="True" id="69" name="Else"/>'


def end_if() -> str:
    return f'{INDENT}<Step enable="True" id="70" name="End If"/>'


def loop() -> str:
    return f'{INDENT}<Step enable="True" id="71" name="Loop"/>'


def end_loop() -> str:
    return f'{INDENT}<Step enable="True" id="73" name="End Loop"/>'


def exit_loop_if(calc: str) -> str:
    return (
        f'{INDENT}<Step enable="True" id="72" name="Exit Loop If">\n'
        f'{INDENT}    <Calculation><![CDATA[{calc}]]></Calculation>\n'
        f'{INDENT}</Step>'
    )


def exit_script(calc: Optional[str] = None) -> str:
    if calc is None:
        return f'{INDENT}<Step enable="True" id="103" name="Exit Script"/>'
    return (
        f'{INDENT}<Step enable="True" id="103" name="Exit Script">\n'
        f'{INDENT}    <Calculation><![CDATA[{calc}]]></Calculation>\n'
        f'{INDENT}</Step>'
    )


def halt_script() -> str:
    return f'{INDENT}<Step enable="True" id="81" name="Halt Script"/>'


# ─── Variables / fields ──────────────────────────────────────────────────────
def set_variable(name: str, calc: str, rep: str = "1") -> str:
    return (
        f'{INDENT}<Step enable="True" id="141" name="Set Variable">\n'
        f'{INDENT}    <Value>\n'
        f'{INDENT}      <Calculation><![CDATA[{calc}]]></Calculation>\n'
        f'{INDENT}    </Value>\n'
        f'{INDENT}    <Repetition>\n'
        f'{INDENT}      <Calculation><![CDATA[{rep}]]></Calculation>\n'
        f'{INDENT}    </Repetition>\n'
        f'{INDENT}    <Name>{_e(name)}</Name>\n'
        f'{INDENT}</Step>'
    )


def set_field(field: FieldRef, calc: str) -> str:
    """Set Field step.

    Args:
        field: ((to_name, to_id), (field_name, field_id))
        calc:  FileMaker calculation expression
    """
    (to_name, _to_id), (fld_name, fld_id) = field
    return (
        f'{INDENT}<Step enable="True" id="76" name="Set Field">\n'
        f'{INDENT}    <Calculation><![CDATA[{calc}]]></Calculation>\n'
        f'{INDENT}    <Field table="{_e(to_name)}" id="{fld_id}" '
        f'name="{_e(fld_name)}"/>\n'
        f'{INDENT}</Step>'
    )


def set_field_by_name(field: FieldRef, target: str) -> str:
    """Set Field By Name. `target` is a name calc; calc still goes in Calculation."""
    (to_name, _to_id), (fld_name, fld_id) = field
    return (
        f'{INDENT}<Step enable="True" id="102" name="Set Field By Name">\n'
        f'{INDENT}    <TargetFieldRef>\n'
        f'{INDENT}      <Calculation><![CDATA[{target}]]></Calculation>\n'
        f'{INDENT}    </TargetFieldRef>\n'
        f'{INDENT}    <Field table="{_e(to_name)}" id="{fld_id}" '
        f'name="{_e(fld_name)}"/>\n'
        f'{INDENT}</Step>'
    )


def insert_calculated_result(field: FieldRef, calc: str, select: bool = False) -> str:
    (to_name, _to_id), (fld_name, fld_id) = field
    sel = "True" if select else "False"
    return (
        f'{INDENT}<Step enable="True" id="78" name="Insert Calculated Result">\n'
        f'{INDENT}    <Select state="{sel}"/>\n'
        f'{INDENT}    <Calculation><![CDATA[{calc}]]></Calculation>\n'
        f'{INDENT}    <Field table="{_e(to_name)}" id="{fld_id}" '
        f'name="{_e(fld_name)}"/>\n'
        f'{INDENT}</Step>'
    )


# ─── Dialogs and error handling ──────────────────────────────────────────────
def show_custom_dialog(title: str, message: str, two_buttons: bool = False) -> str:
    if two_buttons:
        btns = (
            f'{INDENT}    <Buttons>\n'
            f'{INDENT}      <Button CommitState="True">\n'
            f'{INDENT}        <Calculation><![CDATA[OK]]></Calculation>\n'
            f'{INDENT}      </Button>\n'
            f'{INDENT}      <Button CommitState="False">\n'
            f'{INDENT}        <Calculation><![CDATA[Cancel]]></Calculation>\n'
            f'{INDENT}      </Button>\n'
            f'{INDENT}    </Buttons>'
        )
    else:
        btns = (
            f'{INDENT}    <Buttons>\n'
            f'{INDENT}      <Button CommitState="True">\n'
            f'{INDENT}        <Calculation><![CDATA[OK]]></Calculation>\n'
            f'{INDENT}      </Button>\n'
            f'{INDENT}    </Buttons>'
        )
    return (
        f'{INDENT}<Step enable="True" id="87" name="Show Custom Dialog">\n'
        f'{INDENT}    <Title>\n'
        f'{INDENT}      <Calculation><![CDATA[{title}]]></Calculation>\n'
        f'{INDENT}    </Title>\n'
        f'{INDENT}    <Message>\n'
        f'{INDENT}      <Calculation><![CDATA[{message}]]></Calculation>\n'
        f'{INDENT}    </Message>\n'
        f'{btns}\n'
        f'{INDENT}</Step>'
    )


def set_error_capture(on: bool = True) -> str:
    state = "True" if on else "False"
    return (
        f'{INDENT}<Step enable="True" id="86" name="Set Error Capture">\n'
        f'{INDENT}    <State state="{state}"/>\n'
        f'{INDENT}</Step>'
    )


def allow_user_abort(on: bool = False) -> str:
    state = "True" if on else "False"
    return (
        f'{INDENT}<Step enable="True" id="85" name="Allow User Abort">\n'
        f'{INDENT}    <State state="{state}"/>\n'
        f'{INDENT}</Step>'
    )


# ─── Navigation ──────────────────────────────────────────────────────────────
def go_to_layout(layout: LayoutRef) -> str:
    lay_name, lay_id = layout
    return (
        f'{INDENT}<Step enable="True" id="6" name="Go to Layout">\n'
        f'{INDENT}    <LayoutDestination value="SelectedLayout"/>\n'
        f'{INDENT}    <Layout id="{lay_id}" name="{_e(lay_name)}"/>\n'
        f'{INDENT}</Step>'
    )


def go_to_record(target: str = "First") -> str:
    """target ∈ {First, Last, Previous, Next, ByCalculation}"""
    return (
        f'{INDENT}<Step enable="True" id="16" name="Go to Record/Request/Page">\n'
        f'{INDENT}    <Target value="{_e(target)}"/>\n'
        f'{INDENT}</Step>'
    )


def enter_find_mode(pause: bool = False) -> str:
    state = "True" if pause else "False"
    return (
        f'{INDENT}<Step enable="True" id="22" name="Enter Find Mode">\n'
        f'{INDENT}    <Pause state="{state}"/>\n'
        f'{INDENT}</Step>'
    )


def perform_find() -> str:
    return f'{INDENT}<Step enable="True" id="28" name="Perform Find"/>'


def show_all_records() -> str:
    return f'{INDENT}<Step enable="True" id="23" name="Show All Records"/>'


def enter_browse_mode(pause: bool = False) -> str:
    state = "True" if pause else "False"
    return (
        f'{INDENT}<Step enable="True" id="21" name="Enter Browse Mode">\n'
        f'{INDENT}    <Pause state="{state}"/>\n'
        f'{INDENT}</Step>'
    )


# ─── Records ─────────────────────────────────────────────────────────────────
def new_record() -> str:
    return f'{INDENT}<Step enable="True" id="7" name="New Record/Request"/>'


def commit_records(no_dialog: bool = True, skip_validation: bool = False) -> str:
    nd = "True" if no_dialog else "False"
    sv = "True" if skip_validation else "False"
    return (
        f'{INDENT}<Step enable="True" id="75" name="Commit Records/Requests">\n'
        f'{INDENT}    <NoInteract state="{nd}"/>\n'
        f'{INDENT}    <Option state="{sv}"/>\n'
        f'{INDENT}</Step>'
    )


def delete_record(no_dialog: bool = True) -> str:
    nd = "True" if no_dialog else "False"
    return (
        f'{INDENT}<Step enable="True" id="35" name="Delete Record/Request">\n'
        f'{INDENT}    <NoInteract state="{nd}"/>\n'
        f'{INDENT}</Step>'
    )


def delete_portal_row(no_dialog: bool = True) -> str:
    nd = "True" if no_dialog else "False"
    return (
        f'{INDENT}<Step enable="True" id="74" name="Delete Portal Row">\n'
        f'{INDENT}    <NoInteract state="{nd}"/>\n'
        f'{INDENT}</Step>'
    )


# ─── Windows ─────────────────────────────────────────────────────────────────
def new_card_window(name: str, layout: LayoutRef,
                    height: int = 700, width: int = 540,
                    top: int = 80, left: int = 120,
                    close: bool = True, minimize: bool = False,
                    maximize: bool = False, resize: bool = True) -> str:
    """New Window (Card style). `name` is a calc — quote it if it's a string literal."""
    lay_name, lay_id = layout
    def b(x): return "True" if x else "False"
    return (
        f'{INDENT}<Step enable="True" id="122" name="New Window">\n'
        f'{INDENT}    <WindowStyle value="Card"/>\n'
        f'{INDENT}    <Name>\n'
        f'{INDENT}      <Calculation><![CDATA[{name}]]></Calculation>\n'
        f'{INDENT}    </Name>\n'
        f'{INDENT}    <Height>\n'
        f'{INDENT}      <Calculation><![CDATA[{height}]]></Calculation>\n'
        f'{INDENT}    </Height>\n'
        f'{INDENT}    <Width>\n'
        f'{INDENT}      <Calculation><![CDATA[{width}]]></Calculation>\n'
        f'{INDENT}    </Width>\n'
        f'{INDENT}    <Distance>\n'
        f'{INDENT}      <Top><Calculation><![CDATA[{top}]]></Calculation></Top>\n'
        f'{INDENT}      <Left><Calculation><![CDATA[{left}]]></Calculation></Left>\n'
        f'{INDENT}    </Distance>\n'
        f'{INDENT}    <Layout id="{lay_id}" name="{_e(lay_name)}"/>\n'
        f'{INDENT}    <Controls Close="{b(close)}" Minimize="{b(minimize)}" '
        f'Maximize="{b(maximize)}" Resize="{b(resize)}"/>\n'
        f'{INDENT}</Step>'
    )


def new_window(name: str, layout: Optional[LayoutRef] = None,
               style: str = "Document",
               height: int = 600, width: int = 800,
               top: int = 40, left: int = 40,
               close: bool = True, minimize: bool = True,
               maximize: bool = True, resize: bool = True) -> str:
    """style ∈ {Document, FloatingDocument, Dialog, Card}"""
    def b(x): return "True" if x else "False"
    layout_xml = ""
    if layout is not None:
        lay_name, lay_id = layout
        layout_xml = f'\n{INDENT}    <Layout id="{lay_id}" name="{_e(lay_name)}"/>'
    return (
        f'{INDENT}<Step enable="True" id="122" name="New Window">\n'
        f'{INDENT}    <WindowStyle value="{_e(style)}"/>\n'
        f'{INDENT}    <Name>\n'
        f'{INDENT}      <Calculation><![CDATA[{name}]]></Calculation>\n'
        f'{INDENT}    </Name>\n'
        f'{INDENT}    <Height>\n'
        f'{INDENT}      <Calculation><![CDATA[{height}]]></Calculation>\n'
        f'{INDENT}    </Height>\n'
        f'{INDENT}    <Width>\n'
        f'{INDENT}      <Calculation><![CDATA[{width}]]></Calculation>\n'
        f'{INDENT}    </Width>\n'
        f'{INDENT}    <Distance>\n'
        f'{INDENT}      <Top><Calculation><![CDATA[{top}]]></Calculation></Top>\n'
        f'{INDENT}      <Left><Calculation><![CDATA[{left}]]></Calculation></Left>\n'
        f'{INDENT}    </Distance>{layout_xml}\n'
        f'{INDENT}    <Controls Close="{b(close)}" Minimize="{b(minimize)}" '
        f'Maximize="{b(maximize)}" Resize="{b(resize)}"/>\n'
        f'{INDENT}</Step>'
    )


def close_window_current() -> str:
    return (
        f'{INDENT}<Step enable="True" id="121" name="Close Window">\n'
        f'{INDENT}    <LimitToWindowsOfCurrentFile state="True"/>\n'
        f'{INDENT}    <Window value="Current"/>\n'
        f'{INDENT}</Step>'
    )


def freeze_window() -> str:
    return f'{INDENT}<Step enable="True" id="79" name="Freeze Window"/>'


def refresh_window(flush: bool = True) -> str:
    state = "True" if flush else "False"
    return (
        f'{INDENT}<Step enable="True" id="80" name="Refresh Window">\n'
        f'{INDENT}    <FlushJoinResults state="{state}"/>\n'
        f'{INDENT}</Step>'
    )


def refresh_object(name: Optional[str] = None) -> str:
    if name is None:
        return f'{INDENT}<Step enable="True" id="167" name="Refresh Object"/>'
    return (
        f'{INDENT}<Step enable="True" id="167" name="Refresh Object">\n'
        f'{INDENT}    <ObjectName value="{_e(name)}"/>\n'
        f'{INDENT}</Step>'
    )


def refresh_portal(object_name: Optional[str] = None) -> str:
    if object_name is None:
        return f'{INDENT}<Step enable="True" id="168" name="Refresh Portal"/>'
    return (
        f'{INDENT}<Step enable="True" id="168" name="Refresh Portal">\n'
        f'{INDENT}    <ObjectName value="{_e(object_name)}"/>\n'
        f'{INDENT}</Step>'
    )


# ─── Subscript calls ─────────────────────────────────────────────────────────
def perform_script(script: ScriptRef, parameter: str = "") -> str:
    """Perform Script. `parameter` is a calc expression (quote string literals)."""
    sc_name, sc_id = script
    return (
        f'{INDENT}<Step enable="True" id="1" name="Perform Script">\n'
        f'{INDENT}    <Calculation><![CDATA[{parameter}]]></Calculation>\n'
        f'{INDENT}    <Script id="{sc_id}" name="{_e(sc_name)}"/>\n'
        f'{INDENT}</Step>'
    )


# ─── Escape hatch ────────────────────────────────────────────────────────────
def raw_xml(xml_fragment: str) -> str:
    """Drop a hand-built <Step> (or multiple) verbatim into the script body.

    Use this when the spec doesn't cover a step type — your XML must be
    a valid clipboard-format <Step …> element. Indentation is preserved
    as-is; lead with at least two spaces to match other steps if you care.
    """
    return xml_fragment.rstrip()


# ─── Wrapper ─────────────────────────────────────────────────────────────────
def wrap(steps: Iterable[str]) -> str:
    """Wrap an iterable of step strings in the fmxmlsnippet envelope."""
    body = "\n".join(s for s in steps if s)
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<fmxmlsnippet type="FMObjectList">\n'
        f'{body}\n'
        '</fmxmlsnippet>'
    )


def count_steps(snippet: str) -> int:
    """Cheap step counter — counts <Step occurrences in a wrapped snippet."""
    return snippet.count('<Step ')


__all__ = [
    # comment / flow
    "comment", "if_step", "else_if_step", "else_step", "end_if",
    "loop", "end_loop", "exit_loop_if", "exit_script", "halt_script",
    # vars / fields
    "set_variable", "set_field", "set_field_by_name",
    "insert_calculated_result",
    # dialogs / error
    "show_custom_dialog", "set_error_capture", "allow_user_abort",
    # nav
    "go_to_layout", "go_to_record",
    "enter_find_mode", "perform_find", "show_all_records", "enter_browse_mode",
    # records
    "new_record", "commit_records", "delete_record", "delete_portal_row",
    # windows / repaint
    "new_card_window", "new_window", "close_window_current",
    "freeze_window", "refresh_window", "refresh_object", "refresh_portal",
    # subscript
    "perform_script",
    # escape hatch & wrapper
    "raw_xml", "wrap", "count_steps",
]
