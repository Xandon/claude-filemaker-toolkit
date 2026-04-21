#!/usr/bin/env python3
"""
FileMaker DDR Query Tool

Query an indexed FileMaker DDR database for scripts, fields, relationships,
cross-references, and more.

Usage:
    python fm_query.py <db_path> <command> [args...]

Commands:
    script <name|id>           Show a script's human-readable steps
    script-raw <name|id>       Show a script's raw XML steps
    script-refs <name|id>      Show all references TO a script (who calls it)
    script-calls <name|id>     Show all scripts CALLED BY a script
    script-fields <name|id>    Show all fields referenced by a script
    script-layouts <name|id>   Show all layouts used by a script
    scripts [pattern]          List scripts (optional name pattern)
    table <name>               Show table fields
    tables                     List all tables
    field <name>               Find a field across all tables
    field-refs <name>          Show where a field is referenced
    layout <name|id>           Show layout details and script triggers
    layouts [pattern]          List layouts (optional name pattern)
    relationships [table]      Show relationships (optionally for a table)
    value-lists                List value lists
    search <term>              Search across scripts, fields, layouts
    deps <script_name>         Full dependency tree for a script
    summary                    Database summary
"""

import sys
import sqlite3
import argparse
import json
import textwrap


def get_conn(db_path):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def find_script(conn, name_or_id):
    """Find a script by name (case-insensitive, partial match) or ID."""
    c = conn.cursor()
    try:
        sid = int(name_or_id)
        c.execute("SELECT * FROM scripts WHERE script_id=?", (sid,))
        row = c.fetchone()
        if row:
            return row
    except ValueError:
        pass

    # Exact match first
    c.execute("SELECT * FROM scripts WHERE name=? COLLATE NOCASE", (name_or_id,))
    row = c.fetchone()
    if row:
        return row

    # Partial match
    c.execute("SELECT * FROM scripts WHERE name LIKE ? COLLATE NOCASE", (f"%{name_or_id}%",))
    rows = c.fetchall()
    if len(rows) == 1:
        return rows[0]
    elif len(rows) > 1:
        print(f"Multiple scripts match '{name_or_id}':")
        for r in rows:
            print(f"  [{r['script_id']}] {r['name']}")
        print(f"\nBe more specific, or use the script ID.")
        return None

    print(f"No script found matching '{name_or_id}'")
    return None


def cmd_script(conn, name_or_id, raw=False):
    """Display a script's steps in human-readable or raw format."""
    script = find_script(conn, name_or_id)
    if not script:
        return

    sid = script['script_id']
    print(f"\n{'='*70}")
    print(f"Script: {script['name']}  (ID: {sid})")
    print(f"UUID: {script['uuid']}")
    flags = []
    if script['is_hidden']:
        flags.append("Hidden")
    if script['run_with_full_access']:
        flags.append("Run with Full Access")
    if flags:
        print(f"Flags: {', '.join(flags)}")
    print(f"Steps: {script['step_count']}")
    print(f"{'='*70}\n")

    c = conn.cursor()
    c.execute("""SELECT step_index, step_name, step_type_id, enabled, human_readable, raw_xml
                 FROM script_steps WHERE script_id=? ORDER BY step_index""", (sid,))

    indent = 0
    for row in c:
        step_name = row['step_name']
        step_id = row['step_type_id']

        # Adjust indent before printing
        if step_id in (70, 73):  # End If, End Loop
            indent = max(0, indent - 1)
        if step_id in (69, 125):  # Else, Else If
            indent = max(0, indent - 1)

        if raw:
            print(f"[{row['step_index']:3d}] {'  '*indent}{row['raw_xml'][:200]}")
        else:
            prefix = f"[{row['step_index']:3d}] {'  '*indent}"
            print(f"{prefix}{row['human_readable']}")

        # Adjust indent after printing
        if step_id in (68, 125, 69):  # If, Else If, Else
            indent += 1
        if step_id == 71:  # Loop
            indent += 1


def cmd_script_refs(conn, name_or_id):
    """Show all references TO a script (callers)."""
    script = find_script(conn, name_or_id)
    if not script:
        return

    sid = script['script_id']
    print(f"\nReferences to: {script['name']} (ID: {sid})")
    print(f"{'='*70}")

    c = conn.cursor()
    c.execute("""SELECT source_type, source_id, source_name, context
                 FROM script_references WHERE target_script_id=?
                 ORDER BY source_type, source_name""", (sid,))

    refs = c.fetchall()
    if not refs:
        print("  No references found.")
        return

    by_type = {}
    for r in refs:
        st = r['source_type']
        if st not in by_type:
            by_type[st] = []
        by_type[st].append(r)

    for stype, items in by_type.items():
        # Deduplicate
        seen = set()
        unique = []
        for item in items:
            key = (item['source_id'], item['source_name'])
            if key not in seen:
                seen.add(key)
                unique.append(item)

        print(f"\n  From {stype}s ({len(unique)}):")
        for item in unique:
            print(f"    [{item['source_id']}] {item['source_name']}  ({item['context']})")


def cmd_script_calls(conn, name_or_id):
    """Show all scripts called BY a script."""
    script = find_script(conn, name_or_id)
    if not script:
        return

    sid = script['script_id']
    print(f"\nScripts called by: {script['name']} (ID: {sid})")
    print(f"{'='*70}")

    c = conn.cursor()
    c.execute("""SELECT DISTINCT target_script_id, target_script_name
                 FROM script_references WHERE source_type='script' AND source_id=?
                 ORDER BY target_script_name""", (sid,))

    calls = c.fetchall()
    if not calls:
        print("  No script calls found.")
        return

    for call in calls:
        print(f"  [{call['target_script_id']}] {call['target_script_name']}")


def cmd_script_fields(conn, name_or_id):
    """Show fields referenced by a script."""
    script = find_script(conn, name_or_id)
    if not script:
        return

    sid = script['script_id']
    print(f"\nFields used by: {script['name']} (ID: {sid})")
    print(f"{'='*70}")

    c = conn.cursor()
    c.execute("""SELECT DISTINCT field_name, table_occurrence, context
                 FROM field_references WHERE source_type='script' AND source_id=?
                 ORDER BY table_occurrence, field_name""", (sid,))

    fields = c.fetchall()
    if not fields:
        print("  No field references found.")
        return

    current_table = None
    for f in fields:
        tbl = f['table_occurrence'] or '(unknown)'
        if tbl != current_table:
            current_table = tbl
            print(f"\n  Table: {tbl}")
        print(f"    {f['field_name']}")


def cmd_script_layouts(conn, name_or_id):
    """Show layouts referenced by a script."""
    script = find_script(conn, name_or_id)
    if not script:
        return

    sid = script['script_id']
    print(f"\nLayouts used by: {script['name']} (ID: {sid})")
    print(f"{'='*70}")

    c = conn.cursor()
    c.execute("""SELECT DISTINCT layout_id, layout_name
                 FROM layout_references WHERE source_type='script' AND source_id=?
                 ORDER BY layout_name""", (sid,))

    layouts = c.fetchall()
    if not layouts:
        print("  No layout references found.")
        return

    for l in layouts:
        print(f"  [{l['layout_id']}] {l['layout_name']}")


def cmd_scripts(conn, pattern=None):
    """List all scripts, optionally filtered by pattern."""
    c = conn.cursor()
    if pattern:
        c.execute("""SELECT script_id, name, is_folder, is_separator, step_count, is_hidden
                     FROM scripts WHERE name LIKE ? COLLATE NOCASE AND is_separator=0
                     ORDER BY name""", (f"%{pattern}%",))
    else:
        c.execute("""SELECT script_id, name, is_folder, is_separator, step_count, is_hidden
                     FROM scripts WHERE is_separator=0
                     ORDER BY name""")

    rows = c.fetchall()
    print(f"\nScripts ({len(rows)}):")
    print(f"{'ID':>6}  {'Steps':>5}  {'Flags':>8}  Name")
    print(f"{'─'*6}  {'─'*5}  {'─'*8}  {'─'*40}")
    for r in rows:
        flags = []
        if r['is_folder']:
            flags.append('folder')
        if r['is_hidden']:
            flags.append('hidden')
        flag_str = ','.join(flags) if flags else ''
        print(f"{r['script_id']:>6}  {r['step_count']:>5}  {flag_str:>8}  {r['name']}")


def cmd_table(conn, name):
    """Show table fields."""
    c = conn.cursor()
    c.execute("SELECT * FROM tables_def WHERE name LIKE ? COLLATE NOCASE", (f"%{name}%",))
    tables = c.fetchall()

    if not tables:
        print(f"No table found matching '{name}'")
        return

    for tbl in tables:
        print(f"\nTable: {tbl['name']}  (ID: {tbl['table_id']}, Fields: {tbl['field_count']})")
        print(f"{'='*70}")

        c.execute("""SELECT field_id, name, fieldtype, datatype, is_global, calculation_text, comment
                     FROM fields WHERE table_name=? ORDER BY field_id""",
                  (tbl['name'],))

        print(f"{'ID':>5}  {'Type':>10}  {'DataType':>10}  {'G':>1}  Name")
        print(f"{'─'*5}  {'─'*10}  {'─'*10}  {'─'*1}  {'─'*40}")
        for f in c:
            g = 'G' if f['is_global'] else ''
            name_str = f['name']
            if f['calculation_text']:
                calc_preview = f['calculation_text'][:50].replace('\n', ' ')
                name_str += f"  = {calc_preview}"
            if f['comment']:
                name_str += f"  // {f['comment'][:40]}"
            print(f"{f['field_id']:>5}  {f['fieldtype']:>10}  {f['datatype']:>10}  {g:>1}  {name_str}")


def cmd_tables(conn):
    """List all tables."""
    c = conn.cursor()
    c.execute("SELECT table_id, name, field_count FROM tables_def ORDER BY name")
    rows = c.fetchall()
    print(f"\nTables ({len(rows)}):")
    print(f"{'ID':>5}  {'Fields':>6}  Name")
    print(f"{'─'*5}  {'─'*6}  {'─'*30}")
    for r in rows:
        print(f"{r['table_id']:>5}  {r['field_count']:>6}  {r['name']}")


def cmd_field(conn, name):
    """Find a field across all tables."""
    c = conn.cursor()
    c.execute("""SELECT table_name, field_id, name, fieldtype, datatype, is_global, calculation_text
                 FROM fields WHERE name LIKE ? COLLATE NOCASE ORDER BY table_name, name""",
              (f"%{name}%",))
    rows = c.fetchall()
    if not rows:
        print(f"No field found matching '{name}'")
        return

    print(f"\nFields matching '{name}' ({len(rows)}):")
    current_table = None
    for r in rows:
        if r['table_name'] != current_table:
            current_table = r['table_name']
            print(f"\n  Table: {current_table}")
        calc = ""
        if r['calculation_text']:
            calc = f"  = {r['calculation_text'][:60].replace(chr(10), ' ')}"
        g = ' [Global]' if r['is_global'] else ''
        print(f"    [{r['field_id']}] {r['name']} ({r['fieldtype']}/{r['datatype']}){g}{calc}")


def cmd_field_refs(conn, name):
    """Show where a field is referenced."""
    c = conn.cursor()
    c.execute("""SELECT source_type, source_id, source_name, table_occurrence, context
                 FROM field_references WHERE field_name LIKE ? COLLATE NOCASE
                 ORDER BY source_type, source_name""", (f"%{name}%",))
    rows = c.fetchall()
    if not rows:
        print(f"No references found for field '{name}'")
        return

    print(f"\nReferences to field '{name}' ({len(rows)}):")
    by_type = {}
    for r in rows:
        st = r['source_type']
        if st not in by_type:
            by_type[st] = []
        by_type[st].append(r)

    for stype, items in by_type.items():
        seen = set()
        unique = []
        for item in items:
            key = (item['source_id'], item['source_name'], item['table_occurrence'])
            if key not in seen:
                seen.add(key)
                unique.append(item)
        print(f"\n  From {stype}s ({len(unique)}):")
        for item in unique:
            tbl = f" ({item['table_occurrence']})" if item['table_occurrence'] else ""
            print(f"    [{item['source_id']}] {item['source_name']}{tbl}")


def cmd_layout(conn, name_or_id):
    """Show layout details."""
    c = conn.cursor()
    try:
        lid = int(name_or_id)
        c.execute("SELECT * FROM layouts WHERE layout_id=?", (lid,))
    except ValueError:
        c.execute("SELECT * FROM layouts WHERE name LIKE ? COLLATE NOCASE", (f"%{name_or_id}%",))

    rows = c.fetchall()
    if not rows:
        print(f"No layout found matching '{name_or_id}'")
        return

    for l in rows:
        print(f"\nLayout: {l['name']}  (ID: {l['layout_id']})")
        print(f"Table Occurrence: {l['table_occurrence']}")
        print(f"Width: {l['width']}")
        print(f"{'='*70}")

        # Script triggers on this layout
        c2 = conn.cursor()
        c2.execute("""SELECT DISTINCT target_script_id, target_script_name, context
                      FROM script_references WHERE source_type='layout' AND source_id=?
                      ORDER BY target_script_name""", (l['layout_id'],))
        scripts = c2.fetchall()
        if scripts:
            print(f"\n  Script References ({len(scripts)}):")
            for s in scripts:
                print(f"    [{s['target_script_id']}] {s['target_script_name']}  ({s['context']})")

        # Fields on this layout
        c2.execute("""SELECT DISTINCT field_name, table_occurrence
                      FROM field_references WHERE source_type='layout' AND source_id=?
                      ORDER BY table_occurrence, field_name""", (l['layout_id'],))
        fields = c2.fetchall()
        if fields:
            print(f"\n  Fields ({len(fields)}):")
            current_tbl = None
            for f in fields:
                tbl = f['table_occurrence'] or '(unknown)'
                if tbl != current_tbl:
                    current_tbl = tbl
                    print(f"    Table: {tbl}")
                print(f"      {f['field_name']}")


def cmd_layouts(conn, pattern=None):
    """List layouts."""
    c = conn.cursor()
    if pattern:
        c.execute("SELECT layout_id, name, table_occurrence FROM layouts WHERE name LIKE ? COLLATE NOCASE ORDER BY name",
                  (f"%{pattern}%",))
    else:
        c.execute("SELECT layout_id, name, table_occurrence FROM layouts ORDER BY name")

    rows = c.fetchall()
    print(f"\nLayouts ({len(rows)}):")
    print(f"{'ID':>5}  {'Table':>20}  Name")
    print(f"{'─'*5}  {'─'*20}  {'─'*40}")
    for r in rows:
        print(f"{r['layout_id']:>5}  {(r['table_occurrence'] or ''):>20}  {r['name']}")


def cmd_relationships(conn, table=None):
    """Show relationships."""
    c = conn.cursor()
    if table:
        c.execute("""SELECT * FROM relationships
                     WHERE left_table LIKE ? OR right_table LIKE ?
                     ORDER BY left_table, right_table""",
                  (f"%{table}%", f"%{table}%"))
    else:
        c.execute("SELECT * FROM relationships ORDER BY left_table, right_table")

    rows = c.fetchall()
    print(f"\nRelationships ({len(rows)}):")
    for r in rows:
        cascade = ""
        if r['cascade_create']:
            cascade += " [cascade create]"
        if r['cascade_delete']:
            cascade += " [cascade delete]"
        print(f"  {r['left_table']}::{r['left_field']}  {r['join_type']}  {r['right_table']}::{r['right_field']}{cascade}")


def cmd_value_lists(conn):
    """List value lists."""
    c = conn.cursor()
    c.execute("SELECT vl_id, name FROM value_lists ORDER BY name")
    rows = c.fetchall()
    print(f"\nValue Lists ({len(rows)}):")
    for r in rows:
        print(f"  [{r['vl_id']}] {r['name']}")


def cmd_table_occurrences(conn, pattern=None):
    """List table occurrences, optionally filtered by name pattern."""
    c = conn.cursor()
    try:
        if pattern:
            c.execute("""SELECT to_id, name, base_table_name, base_table_id
                         FROM table_occurrences WHERE name LIKE ? ORDER BY name""",
                      (f'%{pattern}%',))
        else:
            c.execute("""SELECT to_id, name, base_table_name, base_table_id
                         FROM table_occurrences ORDER BY name""")
        rows = c.fetchall()
        if not rows:
            print("No table occurrences found." + (f" (filter: '{pattern}')" if pattern else ""))
            return

        print(f"\nTable Occurrences ({len(rows)}):")
        for r in rows:
            base = f" -> {r['base_table_name']}" if r['base_table_name'] != r['name'] else ""
            print(f"  [{r['to_id']:4d}] {r['name']}{base}")
    except Exception:
        print("Table occurrences not indexed. Re-index with updated parser.")


def cmd_table_occurrence(conn, name):
    """Show details for a specific table occurrence."""
    c = conn.cursor()
    try:
        c.execute("SELECT * FROM table_occurrences WHERE name LIKE ? OR to_id=?",
                  (f'%{name}%', int(name) if name.isdigit() else -1))
        to = c.fetchone()
        if not to:
            print(f"Table occurrence '{name}' not found.")
            return

        print(f"\nTable Occurrence: {to['name']}")
        print(f"  ID:         {to['to_id']}")
        print(f"  Base Table: {to['base_table_name']} (id={to['base_table_id']})")
        print(f"  UUID:       {to['uuid']}")

        # Show relationships involving this TO
        c.execute("""SELECT * FROM relationships
                     WHERE left_table=? OR right_table=?""",
                  (to['name'], to['name']))
        rels = c.fetchall()
        if rels:
            print(f"\n  Relationships ({len(rels)}):")
            for r in rels:
                direction = "->" if r['left_table'] == to['name'] else "<-"
                other = r['right_table'] if r['left_table'] == to['name'] else r['left_table']
                print(f"    {direction} {other}  ({r['left_field']} = {r['right_field']})")

        # Show scripts that reference fields from this TO
        c.execute("""SELECT DISTINCT source_name FROM field_references
                     WHERE table_occurrence=?""", (to['name'],))
        scripts = c.fetchall()
        if scripts:
            print(f"\n  Referenced by scripts ({len(scripts)}):")
            for s in scripts[:15]:
                print(f"    {s['source_name']}")
            if len(scripts) > 15:
                print(f"    ... and {len(scripts) - 15} more")
    except Exception as e:
        print(f"Error querying table occurrence: {e}")


def cmd_custom_functions(conn, pattern=None):
    """List custom functions, optionally filtered by name pattern."""
    c = conn.cursor()
    if pattern:
        c.execute("""SELECT cf_id, name, display, param_count, parameters
                     FROM custom_functions WHERE name LIKE ? ORDER BY name""",
                  (f'%{pattern}%',))
    else:
        c.execute("""SELECT cf_id, name, display, param_count, parameters
                     FROM custom_functions ORDER BY name""")
    rows = c.fetchall()
    if not rows:
        print("No custom functions found." + (f" (filter: '{pattern}')" if pattern else ""))
        return

    # Get usage counts
    c.execute("""SELECT cf_name, COUNT(DISTINCT script_id) as script_count
                 FROM cf_references GROUP BY cf_name""")
    usage = {r['cf_name']: r['script_count'] for r in c.fetchall()}

    print(f"\nCustom Functions ({len(rows)}):" + (f"  (filter: '{pattern}')" if pattern else ""))
    print(f"{'ID':>5}  {'Name':<35} {'Params':>6}  {'Used by':>7}  Signature")
    print(f"{'─'*5}  {'─'*35} {'─'*6}  {'─'*7}  {'─'*40}")
    for r in rows:
        name = r['name']
        display = r['display'] or name
        pcount = r['param_count'] or 0
        scripts_using = usage.get(name, 0)
        print(f"{r['cf_id']:>5}  {name:<35} {pcount:>6}  {scripts_using:>5}    {display}")


def cmd_custom_function(conn, name):
    """Show detail for a specific custom function including all scripts that use it."""
    c = conn.cursor()
    # Try exact match first, then partial
    c.execute("SELECT * FROM custom_functions WHERE name=?", (name,))
    row = c.fetchone()
    if not row:
        c.execute("SELECT * FROM custom_functions WHERE name LIKE ?", (f'%{name}%',))
        matches = c.fetchall()
        if not matches:
            print(f"Custom function '{name}' not found.")
            return
        if len(matches) > 1:
            print(f"Multiple matches for '{name}':")
            for m in matches:
                print(f"  [{m['cf_id']}] {m['display'] or m['name']}")
            return
        row = matches[0]

    print(f"\n{'='*70}")
    print(f"Custom Function: {row['name']}  (ID: {row['cf_id']})")
    if row['display']:
        print(f"Signature: {row['display']}")
    if row['parameters']:
        print(f"Parameters: {row['parameters']}")
    if row['calculation_text']:
        print(f"\nCalculation:")
        print(f"  {row['calculation_text']}")
    else:
        print(f"\nCalculation: (not included in DDR XML export)")
    print(f"{'='*70}")

    # Show all scripts that reference this CF
    c.execute("""SELECT DISTINCT script_id, script_name
                 FROM cf_references WHERE cf_name=?
                 ORDER BY script_name""", (row['name'],))
    refs = c.fetchall()
    if refs:
        print(f"\nUsed by {len(refs)} scripts:")
        for r in refs:
            print(f"  [{r['script_id']}] {r['script_name']}")
    else:
        print(f"\nNo script references found.")

    # Show step-level detail for first 10 scripts
    c.execute("""SELECT script_id, script_name, step_index
                 FROM cf_references WHERE cf_name=?
                 ORDER BY script_name, step_index LIMIT 30""", (row['name'],))
    step_refs = c.fetchall()
    if step_refs:
        print(f"\nStep-level references (first 30):")
        for r in step_refs:
            print(f"  [{r['script_id']}] {r['script_name']} → step {r['step_index']}")


def cmd_script_cfs(conn, name):
    """Show which custom functions a script uses."""
    script = find_script(conn, name)
    if not script:
        return

    print(f"\nCustom functions used by: {script['name']} (ID: {script['script_id']})")
    print(f"{'='*70}")

    c = conn.cursor()
    c.execute("""SELECT cf_name, step_index FROM cf_references
                 WHERE script_id=? ORDER BY step_index""", (script['script_id'],))
    refs = c.fetchall()
    if not refs:
        print("  No custom function references found.")
        return

    # Group by CF name
    from collections import OrderedDict
    cf_steps = OrderedDict()
    for r in refs:
        cf_steps.setdefault(r['cf_name'], []).append(r['step_index'])

    # Get display signatures
    cf_displays = {}
    for cfn in cf_steps:
        c.execute("SELECT display FROM custom_functions WHERE name=?", (cfn,))
        row = c.fetchone()
        cf_displays[cfn] = row['display'] if row and row['display'] else cfn

    for cfn, steps in cf_steps.items():
        step_list = ', '.join(str(s) for s in steps)
        print(f"\n  {cf_displays[cfn]}")
        print(f"    Steps: {step_list}")


def cmd_search(conn, term):
    """Search across scripts, fields, layouts, and script step content."""
    c = conn.cursor()
    like = f"%{term}%"

    print(f"\nSearching for '{term}'...")
    print(f"{'='*70}")

    # Scripts
    c.execute("SELECT script_id, name FROM scripts WHERE name LIKE ? COLLATE NOCASE AND is_separator=0", (like,))
    scripts = c.fetchall()
    if scripts:
        print(f"\n  Scripts ({len(scripts)}):")
        for s in scripts:
            print(f"    [{s['script_id']}] {s['name']}")

    # Fields
    c.execute("SELECT table_name, field_id, name FROM fields WHERE name LIKE ? COLLATE NOCASE", (like,))
    fields = c.fetchall()
    if fields:
        print(f"\n  Fields ({len(fields)}):")
        for f in fields:
            print(f"    {f['table_name']}::{f['name']} (id:{f['field_id']})")

    # Layouts
    c.execute("SELECT layout_id, name FROM layouts WHERE name LIKE ? COLLATE NOCASE", (like,))
    layouts = c.fetchall()
    if layouts:
        print(f"\n  Layouts ({len(layouts)}):")
        for l in layouts:
            print(f"    [{l['layout_id']}] {l['name']}")

    # Script step content
    c.execute("""SELECT DISTINCT script_id, script_name FROM script_steps
                 WHERE human_readable LIKE ? COLLATE NOCASE""", (like,))
    step_scripts = c.fetchall()
    if step_scripts:
        print(f"\n  Scripts containing '{term}' in steps ({len(step_scripts)}):")
        for s in step_scripts:
            print(f"    [{s['script_id']}] {s['script_name']}")

    # Calculation text in fields
    c.execute("""SELECT table_name, name FROM fields
                 WHERE calculation_text LIKE ? COLLATE NOCASE""", (like,))
    calc_fields = c.fetchall()
    if calc_fields:
        print(f"\n  Calculated fields referencing '{term}' ({len(calc_fields)}):")
        for f in calc_fields:
            print(f"    {f['table_name']}::{f['name']}")


def cmd_deps(conn, name_or_id, depth=0, visited=None):
    """Show full dependency tree for a script."""
    if visited is None:
        visited = set()

    script = find_script(conn, name_or_id)
    if not script:
        return

    sid = script['script_id']
    if sid in visited:
        print(f"{'  '*depth}[{sid}] {script['name']}  (circular ref)")
        return
    visited.add(sid)

    print(f"{'  '*depth}[{sid}] {script['name']}")

    c = conn.cursor()
    c.execute("""SELECT DISTINCT target_script_id, target_script_name
                 FROM script_references WHERE source_type='script' AND source_id=?""", (sid,))

    for call in c.fetchall():
        cmd_deps(conn, str(call['target_script_id']), depth + 1, visited)


def cmd_summary(conn):
    """Show database summary."""
    c = conn.cursor()

    for row in c.execute("SELECT filename, fm_version, locale, indexed_at FROM files"):
        print(f"\nFile: {row['filename']}")
        print(f"FileMaker Version: {row['fm_version']}")
        print(f"Locale: {row['locale']}")
        print(f"Indexed: {row['indexed_at']}")

    stats = {}
    for table, label in [
        ('tables_def', 'Tables'),
        ('fields', 'Fields'),
        ('scripts', 'Scripts (total)'),
        ('script_steps', 'Script Steps'),
        ('layouts', 'Layouts'),
        ('relationships', 'Relationships'),
        ('table_occurrences', 'Table Occurrences'),
        ('value_lists', 'Value Lists'),
        ('script_references', 'Cross-references'),
        ('external_data_sources', 'External Data Sources'),
        ('custom_functions', 'Custom Functions'),
    ]:
        c.execute(f"SELECT COUNT(*) FROM {table}")
        count = c.fetchone()[0]
        stats[label] = count

    print(f"\n{'='*40}")
    for label, count in stats.items():
        print(f"  {label:.<30} {count}")

    # Top scripts by step count
    c.execute("""SELECT name, step_count FROM scripts
                 WHERE step_count > 0 AND is_separator=0 AND is_folder=0
                 ORDER BY step_count DESC LIMIT 10""")
    print(f"\nLargest Scripts:")
    for r in c:
        print(f"  {r['step_count']:>4} steps  {r['name']}")

    # Most referenced scripts
    c.execute("""SELECT target_script_name, COUNT(*) as ref_count
                 FROM script_references GROUP BY target_script_id
                 ORDER BY ref_count DESC LIMIT 10""")
    print(f"\nMost Referenced Scripts:")
    for r in c:
        print(f"  {r['ref_count']:>4} refs  {r['target_script_name']}")


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        return

    db_path = sys.argv[1]
    command = sys.argv[2]
    args = sys.argv[3:]

    conn = get_conn(db_path)

    try:
        if command == 'script':
            cmd_script(conn, ' '.join(args) if args else '')
        elif command == 'script-raw':
            cmd_script(conn, ' '.join(args) if args else '', raw=True)
        elif command == 'script-refs':
            cmd_script_refs(conn, ' '.join(args) if args else '')
        elif command == 'script-calls':
            cmd_script_calls(conn, ' '.join(args) if args else '')
        elif command == 'script-fields':
            cmd_script_fields(conn, ' '.join(args) if args else '')
        elif command == 'script-layouts':
            cmd_script_layouts(conn, ' '.join(args) if args else '')
        elif command == 'scripts':
            cmd_scripts(conn, ' '.join(args) if args else None)
        elif command == 'table':
            cmd_table(conn, ' '.join(args) if args else '')
        elif command == 'tables':
            cmd_tables(conn)
        elif command == 'field':
            cmd_field(conn, ' '.join(args) if args else '')
        elif command == 'field-refs':
            cmd_field_refs(conn, ' '.join(args) if args else '')
        elif command == 'layout':
            cmd_layout(conn, ' '.join(args) if args else '')
        elif command == 'layouts':
            cmd_layouts(conn, ' '.join(args) if args else None)
        elif command == 'relationships':
            cmd_relationships(conn, ' '.join(args) if args else None)
        elif command == 'value-lists':
            cmd_value_lists(conn)
        elif command == 'tos':
            cmd_table_occurrences(conn, ' '.join(args) if args else None)
        elif command == 'to':
            cmd_table_occurrence(conn, ' '.join(args) if args else '')
        elif command in ('custom-functions', 'cfs'):
            cmd_custom_functions(conn, ' '.join(args) if args else None)
        elif command in ('custom-function', 'cf'):
            cmd_custom_function(conn, ' '.join(args) if args else '')
        elif command == 'script-cfs':
            cmd_script_cfs(conn, ' '.join(args) if args else '')
        elif command == 'search':
            cmd_search(conn, ' '.join(args) if args else '')
        elif command == 'deps':
            cmd_deps(conn, ' '.join(args) if args else '')
        elif command == 'summary':
            cmd_summary(conn)
        else:
            print(f"Unknown command: {command}")
            print(__doc__)
    finally:
        conn.close()


if __name__ == '__main__':
    main()
