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
import sqlite3
import json
import argparse
import html
from datetime import datetime
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
        c.execute("""SELECT cr.cf_name, cr.step_index, cf.display, cf.param_count, cf.parameters
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

    # Build step lookup by script_id for fix XML generation
    steps_by_script = {}
    for sd in scripts_data:
        steps_by_script[sd['script_id']] = {s['index']: s for s in sd['steps']}

    # Generate fix_xml for each finding using one of these methods:
    #   1. fix_xml already in JSON — use as-is (pre-authored clipboard XML)
    #   2. fix_step_indices — pick/reorder existing steps from the script
    #   3. after_steps — generate new steps from fm_xml_gen templates
    missing_fix_xml = []  # list of (finding_id, finding_title, script_id)
    for finding in review['findings']:
        if 'fix' not in finding:
            continue
        for sid_str, fix_data in finding['fix'].items():
            sid = int(sid_str)
            if 'fix_xml' in fix_data:
                continue  # Already has pre-authored fix XML
            if sid not in steps_by_script:
                continue

            if 'fix_step_indices' in fix_data:
                # Reorder/pick existing steps from the script
                raw_list = []
                for step_idx in fix_data['fix_step_indices']:
                    step = steps_by_script[sid].get(step_idx)
                    if step:
                        raw_list.append(step['raw_xml'])
                if raw_list:
                    fix_data['fix_xml'] = convert_script_steps(raw_list)

            elif 'after_steps' in fix_data:
                # Generate new steps from templates
                from fm_xml_gen import generate_step_xml
                step_xmls = []
                for step_def in fix_data['after_steps']:
                    sd = dict(step_def)  # copy to avoid mutating
                    stype = sd.pop('type')
                    step_xmls.append(generate_step_xml(stype, **sd))
                fix_data['fix_xml'] = convert_script_steps(step_xmls)

            # If we got here with no fix_xml AND there's an after_human block,
            # the user is about to see a "Text only" Copy button. Track it so
            # we can warn loudly.
            if 'fix_xml' not in fix_data and fix_data.get('after_human'):
                missing_fix_xml.append(
                    (finding.get('id', '?'), finding.get('title', '(untitled)'), sid)
                )

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

    # Loud warning when fixes don't carry paste-ready XML.
    if missing_fix_xml:
        print()
        print(f"  ⚠️  WARNING: {len(missing_fix_xml)} fix(es) have after_human but no paste-ready XML.")
        print(f"     The user will see a 'Copy Fix Text' button (text-only — they must")
        print(f"     hand-translate the fix back into FileMaker). To produce paste-ready")
        print(f"     XML, add one of {{fix_xml, after_steps, fix_step_indices}} to each:")
        for fid, title, sid in missing_fix_xml:
            print(f"       - Finding #{fid} (script_id {sid}): {title}")
        print(f"     Best default: 'after_steps' — see SKILL.md.")


def main():
    parser = argparse.ArgumentParser(
        description='Generate interactive HTML code review from FileMaker DDR analysis')
    parser.add_argument('db_path', help='Path to indexed SQLite database')
    parser.add_argument('review_json', help='Path to review definition JSON file')
    parser.add_argument('--output', '-o', default='code_review.html',
                        help='Output HTML file path (default: code_review.html)')
    parser.add_argument('--template', '-t', default=None,
                        help='Custom HTML template path (default: templates/review_template.html)')

    args = parser.parse_args()

    if not os.path.exists(args.db_path):
        print(f"Error: Database not found: {args.db_path}")
        sys.exit(1)
    if not os.path.exists(args.review_json):
        print(f"Error: Review JSON not found: {args.review_json}")
        sys.exit(1)

    generate_review_html(args.db_path, args.review_json, args.output, args.template)


if __name__ == '__main__':
    main()
