#!/usr/bin/env python3
"""
FileMaker Script Code Review HTML Generator

Reads a review definition JSON and an indexed SQLite database, then generates
a self-contained HTML file that visualizes the code review interactively.

Usage:
    python fm_review_gen.py <db_path> <review_json> [--output review.html]
    python fm_review_gen.py <db_path> <review_json> --output review.html --template custom.html
"""

import sys
import os
import re
import sqlite3
import json
import argparse
import html
from datetime import datetime
from fnmatch import fnmatch
from fm_ddr_to_clipboard import convert_step, convert_script_steps


def get_script_data(conn, script_id):
    """Fetch full script data from the indexed database."""
    c = conn.cursor()
    c.execute("SELECT * FROM scripts WHERE script_id=?", (script_id,))
    script = c.fetchone()
    if not script:
        print(f"Warning: Script ID {script_id} not found in database")
        return None

    # Get steps
    c.execute("""SELECT step_index, step_name, step_type_id, enabled, human_readable, raw_xml
                 FROM script_steps WHERE script_id=? ORDER BY step_index""", (script_id,))
    steps = []
    for row in c:
        steps.append({
            "index": row[0],
            "step_name": row[1],
            "step_type_id": row[2],
            "enabled": bool(row[3]),
            "human_readable": row[4],
            "raw_xml": row[5]
        })

    # Get callers (script_references where this script is the target)
    c.execute("""SELECT source_type, source_id, source_name, context
                 FROM script_references WHERE target_script_id=?
                 ORDER BY source_type, source_name""", (script_id,))
    called_from = []
    seen = set()
    for row in c:
        key = (row[1], row[2])
        if key not in seen:
            seen.add(key)
            called_from.append({
                "id": row[1],
                "name": row[2],
                "context": f"{row[0]}/{row[3]}"
            })

    # Get sub-scripts called by this script
    c.execute("""SELECT DISTINCT target_script_id, target_script_name
                 FROM script_references WHERE source_type='script' AND source_id=?
                 ORDER BY target_script_name""", (script_id,))
    sub_scripts = [{"id": row[0], "name": row[1]} for row in c]

    # Get custom functions used by this script
    custom_functions = []
    try:
        c.execute("""SELECT cr.cf_name, cr.step_index, cf.display, cf.param_count, cf.parameters, cf.calculation_text
                     FROM cf_references cr
                     LEFT JOIN custom_functions cf ON cr.cf_name = cf.name
                     WHERE cr.script_id=?
                     ORDER BY cr.step_index""", (script_id,))
        # Group by CF name
        cf_map = {}
        for row in c:
            name = row[0]
            if name not in cf_map:
                cf_map[name] = {
                    "name": name,
                    "display": row[2] or name,
                    "param_count": row[3] or 0,
                    "parameters": row[4] or '',
                    "body": row[5] or '',
                    "steps": []
                }
            cf_map[name]["steps"].append(row[1])

        # Get usage count across entire solution for each CF
        for cf_name, cf_data in cf_map.items():
            c.execute("SELECT COUNT(DISTINCT script_id) FROM cf_references WHERE cf_name=?", (cf_name,))
            cf_data["used_by_scripts"] = c.fetchone()[0]

        custom_functions = list(cf_map.values())
    except Exception:
        # cf_references table may not exist in older databases
        pass

    # Build full FMObjectList XML
    full_xml = build_script_xml(script, steps)

    return {
        "script_id": script_id,
        "name": script[3],  # name column
        "uuid": script[4],  # uuid column
        "step_count": script[9],  # step_count column
        "flags": {
            "hidden": bool(script[7]),  # is_hidden
            "full_access": bool(script[8])  # run_with_full_access
        },
        "called_from": called_from,
        "sub_scripts": sub_scripts,
        "custom_functions": custom_functions,
        "steps": steps,
        "full_xml": full_xml
    }


def build_script_xml(script_row, steps):
    """Build clipboard-compatible FMObjectList XML for a script's steps.

    Converts each step from DDR format to FileMaker clipboard format using
    the fm_ddr_to_clipboard converter.
    """
    raw_list = [step['raw_xml'] for step in steps]
    return convert_script_steps(raw_list)


def _parse_human_step(text):
    """Parse a human-readable FileMaker script step into (step_type, kwargs)
    compatible with fm_xml_gen.generate_step_xml().

    Returns (step_type, kwargs) tuple, or None if unrecognised.

    Recognised patterns (case-insensitive):
        # comment text
        Set Error Capture [ On/Off ]
        Allow User Abort [ On/Off ]
        Set Variable [ $name ; Value: expr ]
        Set Variable [ $name ; Value: expr ; Repetition: n ]
        Set Field [ table::field ; value ]
        If [ condition ]
        Else If [ condition ]
        Else
        End If
        Loop
        End Loop
        Exit Loop If [ condition ]
        Go to Layout [ "name" ]
        Perform Script [ "name" ]
        Perform Script [ "name" ; Parameter: expr ]
        Perform Find / Perform Find []
        Enter Find Mode
        New Record/Request
        Commit Records/Requests
        Show All Records
        Freeze Window
        Refresh Window
        Exit Script / Exit Script [ result ]
        Go to Record/Request/Page [ First/Last/Next/Previous ]
        Show Custom Dialog [ "title" ; "message" ]
        Delete Record/Request
        Go to Object [ "name" ]
    """
    text = text.strip()
    if not text:
        return None

    # ── Comment ──
    if text.startswith('#') or text.startswith('//'):
        return ('comment', {'text': text.lstrip('#/ ').strip()})

    # ── Set Error Capture [ On/Off ] ──
    m = re.match(r'Set\s+Error\s+Capture\s*\[\s*(On|Off)\s*\]', text, re.IGNORECASE)
    if m:
        return ('set_error_capture', {'on': 'True' if m.group(1).lower() == 'on' else 'False'})

    # ── Allow User Abort [ On/Off ] ──
    m = re.match(r'Allow\s+User\s+Abort\s*\[\s*(On|Off)\s*\]', text, re.IGNORECASE)
    if m:
        return ('allow_user_abort', {'on': 'True' if m.group(1).lower() == 'on' else 'False'})

    # ── Set Variable [ $name ; Value: expr ; Repetition: n ] ──
    m = re.match(
        r'Set\s+Variable\s*\[\s*(\$\S+)\s*;\s*Value:\s*(.+?)(?:\s*;\s*Repetition:\s*(.+?))?\s*\]$',
        text, re.IGNORECASE)
    if m:
        kwargs = {'name': m.group(1), 'value': m.group(2).strip()}
        if m.group(3):
            kwargs['rep'] = m.group(3).strip()
        return ('set_variable', kwargs)

    # ── Set Field [ table::field ; value ] ──
    m = re.match(r'Set\s+Field\s*\[\s*(.+?)::(.+?)\s*;\s*(.+?)\s*\]', text, re.IGNORECASE)
    if m:
        return ('set_field', {'table': m.group(1).strip(), 'field': m.group(2).strip(),
                              'value': m.group(3).strip()})

    # ── Else If [ condition ] (must come before If) ──
    m = re.match(r'Else\s+If\s*\[\s*(.+?)\s*\]$', text, re.IGNORECASE)
    if m:
        return ('else_if', {'condition': m.group(1)})

    # ── If [ condition ] ──
    m = re.match(r'If\s*\[\s*(.+?)\s*\]$', text, re.IGNORECASE)
    if m:
        return ('if', {'condition': m.group(1)})

    # ── Else ──
    if re.match(r'Else\s*$', text, re.IGNORECASE):
        return ('else', {})

    # ── End If ──
    if re.match(r'End\s*If\s*$', text, re.IGNORECASE):
        return ('end_if', {})

    # ── Exit Loop If [ condition ] ──
    m = re.match(r'Exit\s+Loop\s+If\s*\[\s*(.+?)\s*\]$', text, re.IGNORECASE)
    if m:
        return ('exit_loop_if', {'condition': m.group(1)})

    # ── Loop ──
    if re.match(r'Loop\s*$', text, re.IGNORECASE):
        return ('loop', {})

    # ── End Loop ──
    if re.match(r'End\s*Loop\s*$', text, re.IGNORECASE):
        return ('end_loop', {})

    # ── Go to Layout [ "name" ] ──
    m = re.match(r'Go\s+to\s+Layout\s*\[\s*"?([^"\]]+)"?\s*\]', text, re.IGNORECASE)
    if m:
        return ('go_to_layout', {'name': m.group(1).strip()})

    # ── Perform Script [ "name" ; Parameter: expr ] ──
    m = re.match(
        r'Perform\s+Script\s*\[\s*"?([^"\];]+)"?\s*(?:;\s*Parameter:\s*(.+?))?\s*\]',
        text, re.IGNORECASE)
    if m:
        kwargs = {'name': m.group(1).strip()}
        if m.group(2):
            kwargs['param'] = m.group(2).strip()
        return ('perform_script', kwargs)

    # ── Perform Find ──
    if re.match(r'Perform\s+Find\s*(\[\s*\])?\s*$', text, re.IGNORECASE):
        return ('perform_find', {})

    # ── Enter Find Mode ──
    if re.match(r'Enter\s+Find\s+Mode', text, re.IGNORECASE):
        return ('enter_find_mode', {})

    # ── New Record/Request ──
    if re.match(r'New\s+Record', text, re.IGNORECASE):
        return ('new_record', {})

    # ── Commit Records/Requests ──
    if re.match(r'Commit\s+Record', text, re.IGNORECASE):
        return ('commit', {})

    # ── Show All Records ──
    if re.match(r'Show\s+All\s+Records', text, re.IGNORECASE):
        return ('show_all', {})

    # ── Freeze Window ──
    if re.match(r'Freeze\s+Window', text, re.IGNORECASE):
        return ('freeze_window', {})

    # ── Refresh Window ──
    if re.match(r'Refresh\s+Window', text, re.IGNORECASE):
        return ('refresh_window', {})

    # ── Exit Script [ result ] or Exit Script [] or Exit Script ──
    m = re.match(r'Exit\s+Script\s*\[\s*(.+?)\s*\]', text, re.IGNORECASE)
    if m:
        return ('exit_script', {'result': m.group(1)})
    if re.match(r'Exit\s+Script\s*(\[\s*\])?\s*$', text, re.IGNORECASE):
        return ('exit_script', {})

    # ── Go to Record/Request/Page [ First/Last/Next/Previous ] ──
    m = re.match(r'Go\s+to\s+Record.*\[\s*(First|Last|Next|Previous)\s*\]', text, re.IGNORECASE)
    if m:
        return ('go_to_record', {'target': m.group(1).capitalize()})

    # ── Show Custom Dialog [ "title" ; "message" ] ──
    m = re.match(r'Show\s+Custom\s+Dialog\s*\[\s*"([^"]+)"\s*(?:;\s*"([^"]+)")?\s*\]',
                 text, re.IGNORECASE)
    if m:
        kwargs = {'title': m.group(1)}
        if m.group(2):
            kwargs['message'] = m.group(2)
        return ('show_custom_dialog', kwargs)

    # ── Delete Record/Request ──
    if re.match(r'Delete\s+Record', text, re.IGNORECASE):
        return ('delete_record', {})

    # ── Go to Object [ "name" ] ──
    m = re.match(r'Go\s+to\s+Object\s*\[\s*"?([^"\]]+)"?\s*\]', text, re.IGNORECASE)
    if m:
        return ('go_to_object', {'object_name': m.group(1).strip()})

    # ── Open URL [ url ] ──
    m = re.match(r'Open\s+URL\s*\[\s*(.+?)\s*\]', text, re.IGNORECASE)
    if m:
        return ('open_url', {'url': m.group(1).strip().strip('"')})

    return None


def _normalize_findings(findings, scripts_data):
    """Normalize findings from the flat JSON format to the nested format
    the template expects, and auto-generate before/after code snippets.

    The review JSON can use either format:
      A) Flat format (simple, what the agent writes):
         {
           "script_ids": [2937],
           "step_indices": [15, 16, 17],
           "fix_xml": "<xml>...",
           "fix_step_indices": [15, 16, 17],
           "after_steps": ["Step 15: ...", "Step 16: ..."]
         }
      B) Nested format (what the template expects):
         {
           "script_ids": [2937],
           "affected_steps": { "2937": [15, 16, 17] },
           "fix": { "2937": { "before_human": "...", "after_human": "...", "fix_xml": "..." } }
         }

    This function bridges the gap by converting A→B and auto-generating
    before_human/after_human from the actual script step data.
    """
    # Build step lookup
    steps_by_script = {}
    for sd in scripts_data:
        steps_by_script[sd['script_id']] = {s['index']: s for s in sd['steps']}

    for finding in findings:
        script_ids = finding.get('script_ids', [])

        # ── Normalize affected_steps ──
        if 'affected_steps' not in finding:
            step_indices = finding.get('step_indices', [])
            if step_indices and script_ids:
                finding['affected_steps'] = {}
                for sid in script_ids:
                    finding['affected_steps'][str(sid)] = step_indices
            else:
                finding['affected_steps'] = {}

        # ── Normalize fix structure ──
        if 'fix' not in finding:
            finding['fix'] = {}

        # Handle flat fix_xml / fix_step_indices / after_steps at finding level
        flat_fix_xml = finding.pop('fix_xml', None)
        flat_fix_step_indices = finding.pop('fix_step_indices', None)
        flat_after_steps = finding.pop('after_steps', None)

        for sid in script_ids:
            sid_str = str(sid)

            # Initialize fix entry for this script if not present
            if sid_str not in finding['fix']:
                finding['fix'][sid_str] = {}

            fix_data = finding['fix'][sid_str]

            # Promote flat fields into the nested fix structure
            if flat_fix_xml and 'fix_xml' not in fix_data:
                fix_data['fix_xml'] = flat_fix_xml
            if flat_fix_step_indices and 'fix_step_indices' not in fix_data:
                fix_data['fix_step_indices'] = flat_fix_step_indices
            if flat_after_steps and 'after_steps' not in fix_data:
                fix_data['after_steps'] = flat_after_steps

            # ── Auto-generate before_human from actual script steps ──
            if 'before_human' not in fix_data and sid in steps_by_script:
                affected = finding['affected_steps'].get(sid_str, [])
                if affected:
                    lines = []
                    for idx in affected:
                        step = steps_by_script[sid].get(idx)
                        if step:
                            lines.append(step['human_readable'])
                    if lines:
                        fix_data['before_human'] = '\n'.join(lines)

            # ── Generate fix_xml from fix_step_indices ──
            if 'fix_xml' not in fix_data and 'fix_step_indices' in fix_data and sid in steps_by_script:
                raw_list = []
                for step_idx in fix_data['fix_step_indices']:
                    step = steps_by_script[sid].get(step_idx)
                    if step:
                        raw_list.append(step['raw_xml'])
                if raw_list:
                    fix_data['fix_xml'] = convert_script_steps(raw_list)

            # ── Generate fix_xml from after_steps (template definitions) ──
            if 'fix_xml' not in fix_data and 'after_steps' in fix_data:
                after_steps = fix_data['after_steps']
                # after_steps can be either:
                #   - List of strings (human-readable descriptions for display)
                #   - List of dicts with 'type' key (fm_xml_gen template definitions)
                if after_steps and isinstance(after_steps[0], dict) and 'type' in after_steps[0]:
                    try:
                        from fm_xml_gen import generate_step_xml
                        step_xmls = []
                        for step_def in after_steps:
                            sd = dict(step_def)
                            stype = sd.pop('type')
                            step_xmls.append(generate_step_xml(stype, **sd))
                        fix_data['fix_xml'] = convert_script_steps(step_xmls)
                    except Exception:
                        pass

            # ── Generate fix_xml from after_steps (human-readable strings) ──
            # Parse human-readable step text → generate_step_xml() → clipboard XML
            if 'fix_xml' not in fix_data and 'after_steps' in fix_data:
                after_steps = fix_data['after_steps']
                if after_steps and isinstance(after_steps[0], str):
                    try:
                        from fm_xml_gen import generate_step_xml
                        step_xmls = []
                        all_parsed = True
                        for step_text in after_steps:
                            parsed = _parse_human_step(step_text)
                            if parsed:
                                step_type, kwargs = parsed
                                step_xmls.append(generate_step_xml(step_type, **kwargs))
                            else:
                                all_parsed = False
                                break
                        if all_parsed and step_xmls:
                            fix_data['fix_xml'] = convert_script_steps(step_xmls)
                    except Exception:
                        pass

            # ── Auto-generate after_human from after_steps strings ──
            if 'after_human' not in fix_data and 'after_steps' in fix_data:
                after_steps = fix_data['after_steps']
                if after_steps and isinstance(after_steps[0], str):
                    fix_data['after_human'] = '\n'.join(after_steps)

            # Note: we intentionally do NOT fall back to copying the original
            # affected steps as fix_xml. The "Copy Fix XML" button should only
            # appear when we have actual corrected XML (from fix_step_indices,
            # template-based after_steps dicts, or parsed human-readable
            # after_steps strings), not a copy of the broken code.

    return findings


def generate_review_html(db_path, review_json_path, output_path, template_path=None):
    """Main generation function."""
    # Load review definition
    with open(review_json_path, 'r', encoding='utf-8') as f:
        review = json.load(f)

    # Connect to database
    conn = sqlite3.connect(db_path)

    # Fetch script data for each script in the review
    scripts_data = []
    for script_id in review['script_ids']:
        data = get_script_data(conn, script_id)
        if data:
            scripts_data.append(data)

    conn.close()

    # Normalize findings: bridge flat JSON format → nested template format,
    # auto-generate before/after code and fix XML from script data
    review['findings'] = _normalize_findings(review['findings'], scripts_data)

    # Build the REVIEW_DATA object
    review_data = {
        "meta": review['meta'],
        "scripts": scripts_data,
        "findings": review['findings']
    }
    review_data['meta']['generated_at'] = datetime.now().isoformat()

    # Load template
    if template_path:
        tpl_path = template_path
    else:
        # Look for template relative to this script
        script_dir = os.path.dirname(os.path.abspath(__file__))
        tpl_path = os.path.join(script_dir, '..', 'templates', 'review_template.html')

    if not os.path.exists(tpl_path):
        print(f"Error: Template not found at {tpl_path}")
        sys.exit(1)

    with open(tpl_path, 'r', encoding='utf-8') as f:
        template = f.read()

    # Serialize the review data as JSON
    # Escape </script> sequences that could break out of the script tag
    json_str = json.dumps(review_data, indent=2, ensure_ascii=False)
    json_str = json_str.replace('</script>', '<\\/script>')
    json_str = json_str.replace('</Script>', '<\\/Script>')

    # Inject into template
    output_html = template.replace('/*__REVIEW_DATA__*/{}', json_str)

    # Write output
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(output_html)

    # Print summary
    print(f"Review report generated: {output_path}")
    print(f"  Scripts: {len(scripts_data)}")
    print(f"  Findings: {len(review['findings'])}")
    severity_counts = {}
    for finding in review['findings']:
        sev = finding['severity']
        severity_counts[sev] = severity_counts.get(sev, 0) + 1
    for sev, count in sorted(severity_counts.items()):
        print(f"    {sev}: {count}")
    print(f"  File size: {os.path.getsize(output_path) / 1024:.0f} KB")


def generate_bulk_review(db_path, output_path, folder_filter=None, min_steps=1,
                         check_flags=None, template_path=None):
    """Generate a bulk code review based on diagnostic criteria.

    Args:
        db_path: Path to indexed SQLite database
        output_path: Output HTML file path
        folder_filter: Script folder path pattern (e.g., "Admin/*")
        min_steps: Minimum step count threshold for inclusion
        check_flags: List of diagnostic checks to run (e.g., ["no-error-handling", "slow-patterns"])
        template_path: Custom template path (optional)
    """
    conn = sqlite3.connect(db_path)
    c = conn.cursor()

    # Query scripts matching the filter
    if folder_filter:
        c.execute("""SELECT script_id, name, step_count
                     FROM scripts
                     WHERE step_count >= ? AND is_folder = 0
                     ORDER BY step_count DESC""", (min_steps,))
    else:
        c.execute("""SELECT script_id, name, step_count
                     FROM scripts
                     WHERE step_count >= ? AND is_folder = 0
                     ORDER BY step_count DESC""", (min_steps,))

    matching_scripts = []
    for row in c:
        script_id, name, step_count = row[0], row[1], row[2]
        # Apply folder filter as a name pattern if provided
        if folder_filter:
            if not fnmatch(name, folder_filter):
                continue
        matching_scripts.append(script_id)

    if not matching_scripts:
        print("Warning: No scripts matching filter criteria found")
        matching_scripts = []

    print(f"Found {len(matching_scripts)} matching scripts")

    # Run diagnostics checks to generate findings
    findings = []
    check_flags = check_flags or []

    if not check_flags:
        # Default: run all available checks
        check_flags = ["no-error-handling", "slow-patterns", "dead-code"]

    for check in check_flags:
        if check == "no-error-handling":
            findings.extend(_run_check_no_error_handling(conn, matching_scripts))
        elif check == "slow-patterns":
            findings.extend(_run_check_slow_patterns(conn, matching_scripts))
        elif check == "dead-code":
            findings.extend(_run_check_dead_code(conn, matching_scripts))

    # Build review JSON structure
    review = {
        "meta": {
            "title": f"Bulk Code Review: {folder_filter or 'All Scripts'}",
            "description": f"Auto-generated review for {len(matching_scripts)} scripts (min {min_steps} steps)",
            "author": "fm_review_gen bulk mode",
            "checks": check_flags
        },
        "script_ids": matching_scripts,
        "findings": findings
    }

    # Generate HTML using existing pipeline
    conn.close()

    # Write temporary review JSON to /tmp to avoid permission issues
    import tempfile
    with tempfile.NamedTemporaryFile(mode='w', suffix='_review.json', delete=False,
                                      encoding='utf-8') as f:
        json.dump(review, f, indent=2)
        temp_json_path = f.name

    try:
        generate_review_html(db_path, temp_json_path, output_path, template_path)
    finally:
        # Clean up temp JSON
        try:
            os.remove(temp_json_path)
        except OSError:
            pass


def _run_check_no_error_handling(conn, script_ids):
    """Find scripts that use risky operations without error checks."""
    findings = []
    c = conn.cursor()

    risky_steps = [
        'Perform Find', 'Perform Find/Replace', 'Replace Field Contents',
        'Execute SQL', 'Import Records', 'Delete Records'
    ]

    for script_id in script_ids:
        c.execute("""SELECT step_index, step_name FROM script_steps
                     WHERE script_id = ? AND step_name IN ({})
                     ORDER BY step_index""".format(','.join('?' * len(risky_steps))),
                  [script_id] + risky_steps)

        risky_found = []
        for row in c:
            step_idx, step_name = row
            # Check if there's an "On Error Script Step" before the next major step
            c.execute("""SELECT step_name FROM script_steps
                         WHERE script_id = ? AND step_index > ?
                         AND step_name IN ('On Error Script Step', 'Exit Script')
                         LIMIT 1""", (script_id, step_idx))
            next_step = c.fetchone()
            if not next_step or next_step[0] != 'On Error Script Step':
                risky_found.append((step_idx, step_name))

        if risky_found:
            step_indices = [idx for idx, _ in risky_found]
            step_names = list(set(name for _, name in risky_found))
            findings.append({
                "id": f"bulk_no_error_{script_id}",
                "title": f"No error handling for risky operations",
                "severity": "high",
                "script_ids": [script_id],
                "step_indices": step_indices,
                "description": f"Script uses {', '.join(step_names)} without error handling. Add Set Error Capture [On] and check Get(LastError) after risky operations.",
                "best_practice": "Wrap risky operations (Perform Find, Delete Records, Import Records, etc.) with Set Error Capture [On] before and an If [Get(LastError) ≠ 0] check after.",
                "fix_description": f"Add error capture around {', '.join(step_names)} at steps {', '.join(str(s) for s in step_indices[:5])}{'...' if len(step_indices) > 5 else ''}.",
                "fix": {
                    str(script_id): {
                        "fix_step_indices": step_indices
                    }
                }
            })

    return findings


def _run_check_slow_patterns(conn, script_ids):
    """Find scripts with known performance anti-patterns."""
    findings = []
    c = conn.cursor()

    for script_id in script_ids:
        # Check for layout switches inside loops
        c.execute("""
            SELECT DISTINCT ss1.step_index as layout_step
            FROM script_steps ss1
            WHERE ss1.script_id = ? AND ss1.step_name = 'Go to Layout'
            AND EXISTS (
                SELECT 1 FROM script_steps ss2
                WHERE ss2.script_id = ? AND ss2.step_name = 'Loop'
                AND ss2.step_index < ss1.step_index
                AND EXISTS (
                    SELECT 1 FROM script_steps ss3
                    WHERE ss3.script_id = ? AND ss3.step_name = 'End Loop'
                    AND ss3.step_index > ss1.step_index
                )
            )
        """, (script_id, script_id, script_id))

        layout_step = c.fetchone()
        if layout_step:
            findings.append({
                "id": f"bulk_slow_layout_loop_{script_id}",
                "title": "Layout switch inside loop",
                "severity": "high",
                "script_ids": [script_id],
                "step_indices": [layout_step[0]],
                "description": "Moving to a layout inside a Loop reloads layout context on each iteration. Move layout navigation outside the loop.",
                "best_practice": "Navigate to the target layout before entering the loop. If you need data from different layouts, use ExecuteSQL or Set Variable to cache values instead of switching layouts.",
                "fix_description": "Move Go to Layout step before the Loop, or replace with ExecuteSQL to fetch data without layout switch.",
                "fix": {str(script_id): {}}
            })

    return findings


def _run_check_dead_code(conn, script_ids):
    """Find scripts with disabled steps (incomplete refactoring)."""
    findings = []
    c = conn.cursor()

    for script_id in script_ids:
        c.execute("""SELECT COUNT(*), SUM(CASE WHEN enabled=0 THEN 1 ELSE 0 END)
                     FROM script_steps WHERE script_id = ?""", (script_id,))
        row = c.fetchone()
        total_steps, disabled_steps = row[0], row[1] or 0

        if disabled_steps > 0 and (disabled_steps / total_steps) > 0.1:  # >10% disabled
            findings.append({
                "id": f"bulk_dead_code_{script_id}",
                "title": "Disabled steps (dead code)",
                "severity": "medium",
                "script_ids": [script_id],
                "description": f"Script has {disabled_steps} disabled steps ({100*disabled_steps/total_steps:.0f}%). Clean up or remove incomplete refactoring.",
                "best_practice": "Remove disabled steps once you've confirmed they're no longer needed. Commented-out code in scripts obscures intent and complicates maintenance.",
                "fix": {str(script_id): {}}
            })

    return findings


def main():
    parser = argparse.ArgumentParser(
        description='Generate interactive HTML code review from FileMaker DDR analysis')

    subparsers = parser.add_subparsers(dest='command', help='Command to run')

    # Default command (backward compatible)
    default_parser = subparsers.add_parser('review', help='Generate review from JSON definition (default)')
    default_parser.add_argument('db_path', help='Path to indexed SQLite database')
    default_parser.add_argument('review_json', help='Path to review definition JSON file')
    default_parser.add_argument('--output', '-o', default='code_review.html',
                        help='Output HTML file path (default: code_review.html)')
    default_parser.add_argument('--template', '-t', default=None,
                        help='Custom HTML template path (default: templates/review_template.html)')

    # Bulk review command
    bulk_parser = subparsers.add_parser('bulk', help='Generate bulk review based on diagnostics')
    bulk_parser.add_argument('db_path', help='Path to indexed SQLite database')
    bulk_parser.add_argument('--filter', '-f', default=None,
                        help='Script folder path pattern (e.g., "Admin/*")')
    bulk_parser.add_argument('--min-steps', type=int, default=1,
                        help='Minimum step count threshold (default: 1)')
    bulk_parser.add_argument('--checks', '-c', default='no-error-handling,slow-patterns,dead-code',
                        help='Comma-separated diagnostic checks to run (default: no-error-handling,slow-patterns,dead-code)')
    bulk_parser.add_argument('--output', '-o', default='bulk_review.html',
                        help='Output HTML file path (default: bulk_review.html)')
    bulk_parser.add_argument('--template', '-t', default=None,
                        help='Custom HTML template path')

    args = parser.parse_args()

    # Handle backward compatibility: if db_path and review_json are provided directly (no subcommand)
    if not args.command and len(sys.argv) >= 3:
        args.command = 'review'
        args.db_path = sys.argv[1]
        args.review_json = sys.argv[2]
        # Parse remaining args for --output and --template
        if '--output' in sys.argv:
            args.output = sys.argv[sys.argv.index('--output') + 1]
        else:
            args.output = 'code_review.html'
        if '--template' in sys.argv:
            args.template = sys.argv[sys.argv.index('--template') + 1]
        else:
            args.template = None

    if args.command == 'bulk':
        if not os.path.exists(args.db_path):
            print(f"Error: Database not found: {args.db_path}")
            sys.exit(1)

        checks = [c.strip() for c in args.checks.split(',')]
        generate_bulk_review(args.db_path, args.output, args.filter, args.min_steps, checks, args.template)

    else:  # review or default
        if not args.db_path or not args.review_json:
            print("Usage: python fm_review_gen.py <db_path> <review_json> [--output review.html]")
            print("       python fm_review_gen.py bulk <db_path> [--filter PATTERN] [--min-steps N] [--checks FLAGS] [--output bulk_review.html]")
            sys.exit(1)

        if not os.path.exists(args.db_path):
            print(f"Error: Database not found: {args.db_path}")
            sys.exit(1)
        if not os.path.exists(args.review_json):
            print(f"Error: Review JSON not found: {args.review_json}")
            sys.exit(1)

        generate_review_html(args.db_path, args.review_json, args.output, args.template)


if __name__ == '__main__':
    main()
