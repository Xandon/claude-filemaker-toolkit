#!/usr/bin/env python3
"""
FileMaker DDR Diff Tool

Detect changes in FileMaker solutions between snapshots using the step_hash
feature from FM 22 DDR exports. Compare solutions across versions, generate
diff reports, and track structural changes.

Usage:
    python fm_diff.py <db_path> <command> [args...]

Commands:
    snapshot <db_path> [--name <label>]
        Capture the current state of a database as a named snapshot.
        Snapshots are stored as JSON in .fm_db_cache/snapshots/.

    diff <db_path> [--from <snapshot>] [--to <snapshot>]
        Compare two snapshots or a snapshot vs current DB state.
        If --to is omitted, compares against current DB.
        If --from is omitted, uses the most recent snapshot.
        Output shows scripts with changed steps, new/removed scripts,
        new/removed fields, changed custom function bodies, etc.

    report <db_path> [--from <snapshot>] [--format text|json|html]
        Generate a structured change report in the specified format.
        text:   Human-readable summary (default)
        json:   Machine-readable diff
        html:   Self-contained dark-theme HTML report
"""

import sys
import sqlite3
import argparse
import json
import os
import hashlib
from datetime import datetime
from pathlib import Path
from collections import defaultdict


def get_conn(db_path):
    """Create and return a database connection with Row factory."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def get_snapshot_dir(db_path):
    """
    Determine the snapshot directory, creating it if needed.
    Looks for .fm_db_cache/ relative to the DB path.
    """
    db_dir = Path(db_path).parent
    cache_dir = db_dir / ".fm_db_cache" / "snapshots"
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir


def hash_string(s):
    """Generate a SHA256 hash of a string."""
    if s is None:
        return None
    return hashlib.sha256(s.encode()).hexdigest()[:16]


def capture_snapshot(conn, db_path):
    """
    Capture the current state of a FileMaker database.

    Returns a dictionary with:
    - timestamp: ISO 8601 timestamp
    - solution: Solution name (from files table)
    - scripts: {script_id: {name, step_count, step_hashes: [...]}}
    - fields: {table_name: [field_names]}
    - custom_functions: {name: body_hash}
    - table_occurrences: [TO names]
    """
    c = conn.cursor()

    # Get solution name
    c.execute("SELECT DISTINCT filename FROM files LIMIT 1")
    row = c.fetchone()
    solution = row[0] if row else "Unknown"

    # Capture scripts with step hashes
    scripts = {}
    c.execute(
        """
        SELECT s.script_id, s.name, s.step_count,
               GROUP_CONCAT(ss.step_hash) as hashes
        FROM scripts s
        LEFT JOIN script_steps ss ON s.script_id = ss.script_id
        GROUP BY s.script_id
        ORDER BY s.script_id
    """
    )
    for row in c.fetchall():
        script_id = row["script_id"]
        hashes = row["hashes"].split(",") if row["hashes"] else []
        scripts[script_id] = {
            "name": row["name"],
            "step_count": row["step_count"],
            "step_hashes": hashes,
        }

    # Capture fields by table
    fields = defaultdict(list)
    c.execute(
        """
        SELECT DISTINCT table_name, name
        FROM fields
        ORDER BY table_name, name
    """
    )
    for row in c.fetchall():
        fields[row["table_name"]].append(row["name"])

    # Capture custom functions and their bodies
    custom_functions = {}
    c.execute(
        """
        SELECT name, calculation_text
        FROM custom_functions
        ORDER BY name
    """
    )
    for row in c.fetchall():
        body_hash = hash_string(row["calculation_text"])
        custom_functions[row["name"]] = body_hash

    # Capture table occurrences
    table_occurrences = []
    c.execute("SELECT DISTINCT name FROM table_occurrences ORDER BY name")
    for row in c.fetchall():
        table_occurrences.append(row["name"])

    return {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "solution": solution,
        "scripts": scripts,
        "fields": dict(fields),
        "custom_functions": custom_functions,
        "table_occurrences": table_occurrences,
    }


def save_snapshot(snapshot, snapshot_dir, label=None):
    """
    Save a snapshot to disk as JSON.

    If label is provided, use it. Otherwise, generate a timestamp-based filename.
    Returns the filename.
    """
    if label:
        filename = f"{label}.json"
    else:
        timestamp = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
        filename = f"snapshot-{timestamp}.json"

    filepath = snapshot_dir / filename
    with open(filepath, "w") as f:
        json.dump(snapshot, f, indent=2)

    return filename


def load_snapshot(snapshot_dir, snapshot_name):
    """Load a snapshot from disk by name."""
    filepath = snapshot_dir / f"{snapshot_name}.json"
    if not filepath.exists():
        raise FileNotFoundError(f"Snapshot not found: {snapshot_name}")

    with open(filepath, "r") as f:
        return json.load(f)


def get_most_recent_snapshot(snapshot_dir):
    """Get the most recent snapshot filename (without .json extension)."""
    snapshots = list(snapshot_dir.glob("*.json"))
    if not snapshots:
        return None

    # Sort by modification time, most recent first
    snapshots.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return snapshots[0].stem


def compute_diff(old_snapshot, new_snapshot):
    """
    Compare two snapshots and return a structured diff.

    Returns a dict with:
    - scripts_added: [script_ids]
    - scripts_removed: [script_ids]
    - scripts_modified: [{id, name, step_count_change, step_hashes_change}]
    - fields_added: {table: [field_names]}
    - fields_removed: {table: [field_names]}
    - custom_functions_added: [names]
    - custom_functions_removed: [names]
    - custom_functions_modified: [names]
    - table_occurrences_added: [names]
    - table_occurrences_removed: [names]
    """
    diff = {
        "scripts_added": [],
        "scripts_removed": [],
        "scripts_modified": [],
        "fields_added": defaultdict(list),
        "fields_removed": defaultdict(list),
        "custom_functions_added": [],
        "custom_functions_removed": [],
        "custom_functions_modified": [],
        "table_occurrences_added": [],
        "table_occurrences_removed": [],
    }

    old_scripts = old_snapshot.get("scripts", {})
    new_scripts = new_snapshot.get("scripts", {})

    # Compare scripts
    for script_id in new_scripts:
        if script_id not in old_scripts:
            diff["scripts_added"].append(script_id)
        else:
            old_script = old_scripts[script_id]
            new_script = new_scripts[script_id]

            # Check for modifications
            if old_script.get("step_hashes") != new_script.get("step_hashes"):
                diff["scripts_modified"].append(
                    {
                        "id": script_id,
                        "name": new_script.get("name"),
                        "old_step_count": old_script.get("step_count"),
                        "new_step_count": new_script.get("step_count"),
                        "old_hashes": old_script.get("step_hashes", []),
                        "new_hashes": new_script.get("step_hashes", []),
                    }
                )

    for script_id in old_scripts:
        if script_id not in new_scripts:
            diff["scripts_removed"].append(script_id)

    # Compare fields
    old_fields = old_snapshot.get("fields", {})
    new_fields = new_snapshot.get("fields", {})

    for table in new_fields:
        if table not in old_fields:
            diff["fields_added"][table] = new_fields[table]
        else:
            old_field_set = set(old_fields[table])
            new_field_set = set(new_fields[table])
            added = new_field_set - old_field_set
            removed = old_field_set - new_field_set

            if added:
                diff["fields_added"][table] = sorted(list(added))
            if removed:
                diff["fields_removed"][table] = sorted(list(removed))

    for table in old_fields:
        if table not in new_fields:
            diff["fields_removed"][table] = old_fields[table]

    # Compare custom functions
    old_cf = old_snapshot.get("custom_functions", {})
    new_cf = new_snapshot.get("custom_functions", {})

    for cf_name in new_cf:
        if cf_name not in old_cf:
            diff["custom_functions_added"].append(cf_name)
        elif old_cf[cf_name] != new_cf[cf_name]:
            diff["custom_functions_modified"].append(cf_name)

    for cf_name in old_cf:
        if cf_name not in new_cf:
            diff["custom_functions_removed"].append(cf_name)

    # Compare table occurrences
    old_tos = set(old_snapshot.get("table_occurrences", []))
    new_tos = set(new_snapshot.get("table_occurrences", []))

    diff["table_occurrences_added"] = sorted(list(new_tos - old_tos))
    diff["table_occurrences_removed"] = sorted(list(old_tos - new_tos))

    # Convert defaultdicts to regular dicts
    diff["fields_added"] = dict(diff["fields_added"])
    diff["fields_removed"] = dict(diff["fields_removed"])

    return diff


def format_text_report(diff, old_snapshot, new_snapshot):
    """Format a diff as human-readable text."""
    lines = []
    lines.append("=" * 70)
    lines.append("FILEMAKER SOLUTION DIFF REPORT")
    lines.append("=" * 70)
    lines.append("")

    if old_snapshot:
        lines.append(f"From: {old_snapshot.get('solution')} ({old_snapshot.get('timestamp')})")
    lines.append(f"To:   {new_snapshot.get('solution')} ({new_snapshot.get('timestamp')})")
    lines.append("")

    # Scripts
    if diff["scripts_added"] or diff["scripts_removed"] or diff["scripts_modified"]:
        lines.append("SCRIPTS")
        lines.append("-" * 70)

        if diff["scripts_added"]:
            lines.append(f"Added: {len(diff['scripts_added'])} script(s)")
            for sid in diff["scripts_added"]:
                script = new_snapshot["scripts"][sid]
                lines.append(f"  + {script['name']} (ID: {sid}, {script['step_count']} steps)")

        if diff["scripts_removed"]:
            lines.append(f"Removed: {len(diff['scripts_removed'])} script(s)")
            for sid in diff["scripts_removed"]:
                script = old_snapshot["scripts"][sid]
                lines.append(f"  - {script['name']} (ID: {sid}, {script['step_count']} steps)")

        if diff["scripts_modified"]:
            lines.append(f"Modified: {len(diff['scripts_modified'])} script(s)")
            for mod in diff["scripts_modified"]:
                lines.append(
                    f"  ~ {mod['name']} (ID: {mod['id']}): "
                    f"{mod['old_step_count']} → {mod['new_step_count']} steps"
                )
                # Detailed hash comparison
                old_hashes = mod["old_hashes"]
                new_hashes = mod["new_hashes"]
                max_idx = max(len(old_hashes), len(new_hashes))
                for i in range(max_idx):
                    old_h = old_hashes[i] if i < len(old_hashes) else None
                    new_h = new_hashes[i] if i < len(new_hashes) else None
                    if old_h != new_h:
                        if old_h is None:
                            lines.append(f"      Step {i + 1}: [added] {new_h}")
                        elif new_h is None:
                            lines.append(f"      Step {i + 1}: [removed] {old_h}")
                        else:
                            lines.append(
                                f"      Step {i + 1}: {old_h} → {new_h}"
                            )

        lines.append("")

    # Fields
    if diff["fields_added"] or diff["fields_removed"]:
        lines.append("FIELDS")
        lines.append("-" * 70)

        if diff["fields_added"]:
            for table in sorted(diff["fields_added"].keys()):
                fields = diff["fields_added"][table]
                lines.append(f"  {table}:")
                for field in sorted(fields):
                    lines.append(f"    + {field}")

        if diff["fields_removed"]:
            for table in sorted(diff["fields_removed"].keys()):
                fields = diff["fields_removed"][table]
                lines.append(f"  {table}:")
                for field in sorted(fields):
                    lines.append(f"    - {field}")

        lines.append("")

    # Custom Functions
    if (
        diff["custom_functions_added"]
        or diff["custom_functions_removed"]
        or diff["custom_functions_modified"]
    ):
        lines.append("CUSTOM FUNCTIONS")
        lines.append("-" * 70)

        if diff["custom_functions_added"]:
            lines.append(f"Added: {', '.join(sorted(diff['custom_functions_added']))}")

        if diff["custom_functions_removed"]:
            lines.append(f"Removed: {', '.join(sorted(diff['custom_functions_removed']))}")

        if diff["custom_functions_modified"]:
            lines.append(f"Modified: {', '.join(sorted(diff['custom_functions_modified']))}")

        lines.append("")

    # Table Occurrences
    if diff["table_occurrences_added"] or diff["table_occurrences_removed"]:
        lines.append("TABLE OCCURRENCES")
        lines.append("-" * 70)

        if diff["table_occurrences_added"]:
            lines.append("Added:")
            for to in diff["table_occurrences_added"]:
                lines.append(f"  + {to}")

        if diff["table_occurrences_removed"]:
            lines.append("Removed:")
            for to in diff["table_occurrences_removed"]:
                lines.append(f"  - {to}")

        lines.append("")

    # Summary
    lines.append("=" * 70)
    total_changes = (
        len(diff["scripts_added"])
        + len(diff["scripts_removed"])
        + len(diff["scripts_modified"])
        + len(diff["fields_added"])
        + len(diff["fields_removed"])
        + len(diff["custom_functions_added"])
        + len(diff["custom_functions_removed"])
        + len(diff["custom_functions_modified"])
        + len(diff["table_occurrences_added"])
        + len(diff["table_occurrences_removed"])
    )
    lines.append(f"Total changes: {total_changes}")
    lines.append("=" * 70)

    return "\n".join(lines)


def format_json_report(diff, old_snapshot, new_snapshot):
    """Format a diff as JSON."""
    report = {
        "from": old_snapshot if old_snapshot else None,
        "to": new_snapshot,
        "diff": diff,
    }
    return json.dumps(report, indent=2)


def format_html_report(diff, old_snapshot, new_snapshot):
    """Format a diff as a self-contained dark-theme HTML report."""
    html = []
    html.append("<!DOCTYPE html>")
    html.append("<html>")
    html.append("<head>")
    html.append("<meta charset='utf-8'>")
    html.append("<title>FileMaker Solution Diff Report</title>")
    html.append("<style>")
    html.append(
        """
    * {
        margin: 0;
        padding: 0;
        box-sizing: border-box;
    }
    body {
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
        background-color: #1e1e2e;
        color: #e0e0e0;
        line-height: 1.6;
        padding: 40px 20px;
    }
    .container {
        max-width: 1000px;
        margin: 0 auto;
    }
    h1 {
        color: #ffffff;
        margin-bottom: 10px;
        font-size: 2.5em;
    }
    .header-info {
        color: #888;
        font-size: 0.9em;
        margin-bottom: 30px;
        padding-bottom: 20px;
        border-bottom: 1px solid #333;
    }
    h2 {
        color: #ffffff;
        margin-top: 30px;
        margin-bottom: 15px;
        font-size: 1.5em;
        border-bottom: 2px solid #333;
        padding-bottom: 10px;
    }
    .section {
        margin-bottom: 30px;
        background-color: #252535;
        padding: 20px;
        border-radius: 6px;
        border-left: 4px solid #888;
    }
    .section.added {
        border-left-color: #2ecc71;
    }
    .section.removed {
        border-left-color: #e74c3c;
    }
    .section.modified {
        border-left-color: #f39c12;
    }
    .item {
        padding: 10px;
        margin: 8px 0;
        background-color: #1e1e2e;
        border-radius: 4px;
        border-left: 3px solid #666;
    }
    .item.added {
        border-left-color: #2ecc71;
        background-color: rgba(46, 204, 113, 0.05);
    }
    .item.added::before {
        content: "+ ";
        color: #2ecc71;
        font-weight: bold;
    }
    .item.removed {
        border-left-color: #e74c3c;
        background-color: rgba(231, 76, 60, 0.05);
    }
    .item.removed::before {
        content: "- ";
        color: #e74c3c;
        font-weight: bold;
    }
    .item.modified {
        border-left-color: #f39c12;
        background-color: rgba(243, 156, 18, 0.05);
    }
    .item.modified::before {
        content: "~ ";
        color: #f39c12;
        font-weight: bold;
    }
    .item-name {
        font-weight: 500;
        color: #ffffff;
    }
    .item-meta {
        font-size: 0.85em;
        color: #888;
        margin-top: 3px;
    }
    .change-detail {
        margin-left: 20px;
        margin-top: 8px;
        padding: 8px;
        background-color: #1e1e2e;
        border-left: 2px solid #666;
        font-size: 0.9em;
        color: #aaa;
        font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', monospace;
    }
    .summary {
        background-color: #252535;
        padding: 20px;
        border-radius: 6px;
        margin-top: 40px;
        text-align: center;
        border: 1px solid #333;
    }
    .summary-number {
        font-size: 2em;
        font-weight: bold;
        color: #f39c12;
    }
    .summary-label {
        color: #888;
        font-size: 0.9em;
    }
    table {
        width: 100%;
        border-collapse: collapse;
        margin: 15px 0;
    }
    th, td {
        padding: 10px;
        text-align: left;
        border-bottom: 1px solid #333;
    }
    th {
        background-color: #252535;
        color: #ffffff;
        font-weight: 600;
    }
    tr:hover {
        background-color: #2a2a3a;
    }
    .no-changes {
        color: #888;
        font-style: italic;
    }
    """
    )
    html.append("</style>")
    html.append("</head>")
    html.append("<body>")
    html.append("<div class='container'>")

    # Header
    html.append("<h1>FileMaker Solution Diff Report</h1>")
    html.append("<div class='header-info'>")
    if old_snapshot:
        html.append(
            f"<div><strong>From:</strong> {old_snapshot.get('solution')} "
            f"({old_snapshot.get('timestamp')})</div>"
        )
    html.append(
        f"<div><strong>To:</strong> {new_snapshot.get('solution')} "
        f"({new_snapshot.get('timestamp')})</div>"
    )
    html.append("</div>")

    # Scripts section
    if diff["scripts_added"] or diff["scripts_removed"] or diff["scripts_modified"]:
        html.append("<h2>Scripts</h2>")

        if diff["scripts_added"]:
            html.append("<div class='section added'>")
            html.append(f"<h3 style='color: #2ecc71;'>Added Scripts ({len(diff['scripts_added'])})</h3>")
            for sid in diff["scripts_added"]:
                script = new_snapshot["scripts"][sid]
                html.append(
                    f"<div class='item added'><span class='item-name'>{script['name']}</span>"
                    f"<div class='item-meta'>ID: {sid} | {script['step_count']} steps</div></div>"
                )
            html.append("</div>")

        if diff["scripts_removed"]:
            html.append("<div class='section removed'>")
            html.append(f"<h3 style='color: #e74c3c;'>Removed Scripts ({len(diff['scripts_removed'])})</h3>")
            for sid in diff["scripts_removed"]:
                script = old_snapshot["scripts"][sid]
                html.append(
                    f"<div class='item removed'><span class='item-name'>{script['name']}</span>"
                    f"<div class='item-meta'>ID: {sid} | {script['step_count']} steps</div></div>"
                )
            html.append("</div>")

        if diff["scripts_modified"]:
            html.append("<div class='section modified'>")
            html.append(f"<h3 style='color: #f39c12;'>Modified Scripts ({len(diff['scripts_modified'])})</h3>")
            for mod in diff["scripts_modified"]:
                html.append(f"<div class='item modified'><span class='item-name'>{mod['name']}</span>")
                html.append(
                    f"<div class='item-meta'>ID: {mod['id']} | "
                    f"Steps: {mod['old_step_count']} → {mod['new_step_count']}</div>"
                )

                # Step-by-step hash changes
                old_hashes = mod["old_hashes"]
                new_hashes = mod["new_hashes"]
                max_idx = max(len(old_hashes), len(new_hashes))
                for i in range(max_idx):
                    old_h = old_hashes[i] if i < len(old_hashes) else None
                    new_h = new_hashes[i] if i < len(new_hashes) else None
                    if old_h != new_h:
                        if old_h is None:
                            html.append(
                                f"<div class='change-detail' style='color: #2ecc71;'>"
                                f"Step {i + 1}: [added] {new_h}</div>"
                            )
                        elif new_h is None:
                            html.append(
                                f"<div class='change-detail' style='color: #e74c3c;'>"
                                f"Step {i + 1}: [removed] {old_h}</div>"
                            )
                        else:
                            html.append(
                                f"<div class='change-detail'>"
                                f"Step {i + 1}: {old_h} → {new_h}</div>"
                            )

                html.append("</div>")
            html.append("</div>")

    # Fields section
    if diff["fields_added"] or diff["fields_removed"]:
        html.append("<h2>Fields</h2>")

        if diff["fields_added"]:
            html.append("<div class='section added'>")
            html.append("<h3 style='color: #2ecc71;'>Added Fields</h3>")
            for table in sorted(diff["fields_added"].keys()):
                fields = diff["fields_added"][table]
                html.append(f"<div style='margin-bottom: 15px;'>")
                html.append(f"<strong>{table}:</strong><br>")
                for field in sorted(fields):
                    html.append(f"<div class='item added'><span class='item-name'>{field}</span></div>")
                html.append("</div>")
            html.append("</div>")

        if diff["fields_removed"]:
            html.append("<div class='section removed'>")
            html.append("<h3 style='color: #e74c3c;'>Removed Fields</h3>")
            for table in sorted(diff["fields_removed"].keys()):
                fields = diff["fields_removed"][table]
                html.append(f"<div style='margin-bottom: 15px;'>")
                html.append(f"<strong>{table}:</strong><br>")
                for field in sorted(fields):
                    html.append(f"<div class='item removed'><span class='item-name'>{field}</span></div>")
                html.append("</div>")
            html.append("</div>")

    # Custom Functions section
    if (
        diff["custom_functions_added"]
        or diff["custom_functions_removed"]
        or diff["custom_functions_modified"]
    ):
        html.append("<h2>Custom Functions</h2>")

        if diff["custom_functions_added"]:
            html.append("<div class='section added'>")
            html.append("<h3 style='color: #2ecc71;'>Added Custom Functions</h3>")
            for cf in sorted(diff["custom_functions_added"]):
                html.append(f"<div class='item added'><span class='item-name'>{cf}</span></div>")
            html.append("</div>")

        if diff["custom_functions_removed"]:
            html.append("<div class='section removed'>")
            html.append("<h3 style='color: #e74c3c;'>Removed Custom Functions</h3>")
            for cf in sorted(diff["custom_functions_removed"]):
                html.append(f"<div class='item removed'><span class='item-name'>{cf}</span></div>")
            html.append("</div>")

        if diff["custom_functions_modified"]:
            html.append("<div class='section modified'>")
            html.append("<h3 style='color: #f39c12;'>Modified Custom Functions</h3>")
            for cf in sorted(diff["custom_functions_modified"]):
                html.append(f"<div class='item modified'><span class='item-name'>{cf}</span></div>")
            html.append("</div>")

    # Table Occurrences section
    if diff["table_occurrences_added"] or diff["table_occurrences_removed"]:
        html.append("<h2>Table Occurrences</h2>")

        if diff["table_occurrences_added"]:
            html.append("<div class='section added'>")
            html.append("<h3 style='color: #2ecc71;'>Added Table Occurrences</h3>")
            for to in diff["table_occurrences_added"]:
                html.append(f"<div class='item added'><span class='item-name'>{to}</span></div>")
            html.append("</div>")

        if diff["table_occurrences_removed"]:
            html.append("<div class='section removed'>")
            html.append("<h3 style='color: #e74c3c;'>Removed Table Occurrences</h3>")
            for to in diff["table_occurrences_removed"]:
                html.append(f"<div class='item removed'><span class='item-name'>{to}</span></div>")
            html.append("</div>")

    # Summary
    total_changes = (
        len(diff["scripts_added"])
        + len(diff["scripts_removed"])
        + len(diff["scripts_modified"])
        + sum(len(v) for v in diff["fields_added"].values())
        + sum(len(v) for v in diff["fields_removed"].values())
        + len(diff["custom_functions_added"])
        + len(diff["custom_functions_removed"])
        + len(diff["custom_functions_modified"])
        + len(diff["table_occurrences_added"])
        + len(diff["table_occurrences_removed"])
    )

    html.append("<div class='summary'>")
    html.append(f"<div class='summary-number'>{total_changes}</div>")
    html.append("<div class='summary-label'>Total Changes Detected</div>")
    html.append("</div>")

    html.append("</div>")
    html.append("</body>")
    html.append("</html>")

    return "\n".join(html)


def cmd_snapshot(args):
    """Handle the 'snapshot' command."""
    db_path = args.db_path
    label = args.name

    if not os.path.exists(db_path):
        print(f"Error: Database not found: {db_path}", file=sys.stderr)
        sys.exit(1)

    conn = get_conn(db_path)
    snapshot_dir = get_snapshot_dir(db_path)

    print(f"Capturing snapshot from {db_path}...")
    snapshot = capture_snapshot(conn, db_path)
    conn.close()

    filename = save_snapshot(snapshot, snapshot_dir, label)
    filepath = snapshot_dir / filename

    print(f"Snapshot saved: {filepath}")
    print(f"  Solution: {snapshot['solution']}")
    print(f"  Scripts: {len(snapshot['scripts'])}")
    print(f"  Fields: {sum(len(v) for v in snapshot['fields'].values())}")
    print(f"  Custom Functions: {len(snapshot['custom_functions'])}")
    print(f"  Table Occurrences: {len(snapshot['table_occurrences'])}")


def cmd_diff(args):
    """Handle the 'diff' command."""
    db_path = args.db_path
    from_name = args.from_snapshot
    to_name = args.to_snapshot

    if not os.path.exists(db_path):
        print(f"Error: Database not found: {db_path}", file=sys.stderr)
        sys.exit(1)

    snapshot_dir = get_snapshot_dir(db_path)

    # Load or capture the "from" snapshot
    if from_name:
        try:
            old_snapshot = load_snapshot(snapshot_dir, from_name)
        except FileNotFoundError as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)
    else:
        most_recent = get_most_recent_snapshot(snapshot_dir)
        if not most_recent:
            print("Error: No snapshots found. Create one with: snapshot <db_path>", file=sys.stderr)
            sys.exit(1)
        old_snapshot = load_snapshot(snapshot_dir, most_recent)

    # Load or capture the "to" snapshot
    if to_name:
        try:
            new_snapshot = load_snapshot(snapshot_dir, to_name)
        except FileNotFoundError as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)
    else:
        conn = get_conn(db_path)
        new_snapshot = capture_snapshot(conn, db_path)
        conn.close()

    # Compute and display the diff
    diff = compute_diff(old_snapshot, new_snapshot)
    print(format_text_report(diff, old_snapshot, new_snapshot))


def cmd_report(args):
    """Handle the 'report' command."""
    db_path = args.db_path
    from_name = args.from_snapshot
    fmt = args.format

    if not os.path.exists(db_path):
        print(f"Error: Database not found: {db_path}", file=sys.stderr)
        sys.exit(1)

    snapshot_dir = get_snapshot_dir(db_path)

    # Load or capture the "from" snapshot
    old_snapshot = None
    if from_name:
        try:
            old_snapshot = load_snapshot(snapshot_dir, from_name)
        except FileNotFoundError as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)
    else:
        most_recent = get_most_recent_snapshot(snapshot_dir)
        if most_recent:
            old_snapshot = load_snapshot(snapshot_dir, most_recent)

    # Always capture the current DB state
    conn = get_conn(db_path)
    new_snapshot = capture_snapshot(conn, db_path)
    conn.close()

    # Compute the diff
    if old_snapshot:
        diff = compute_diff(old_snapshot, new_snapshot)
    else:
        diff = None

    # Format and output the report
    if fmt == "json":
        output = format_json_report(diff, old_snapshot, new_snapshot)
    elif fmt == "html":
        output = format_html_report(diff, old_snapshot, new_snapshot)
    else:  # text
        if not old_snapshot:
            print("Warning: No snapshot found for comparison. Showing current state only.", file=sys.stderr)
            old_snapshot = None
        output = format_text_report(diff, old_snapshot, new_snapshot)

    print(output)


def main():
    parser = argparse.ArgumentParser(
        description="FileMaker DDR Diff Tool - Detect changes using step_hash",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    subparsers = parser.add_subparsers(dest="command", help="Command to execute")

    # Snapshot command
    snap_parser = subparsers.add_parser("snapshot", help="Capture a database snapshot")
    snap_parser.add_argument("db_path", help="Path to the FileMaker DDR SQLite database")
    snap_parser.add_argument(
        "--name",
        dest="name",
        help="Optional snapshot label (without .json extension)",
    )
    snap_parser.set_defaults(func=cmd_snapshot)

    # Diff command
    diff_parser = subparsers.add_parser("diff", help="Compare two snapshots or snapshot vs current DB")
    diff_parser.add_argument("db_path", help="Path to the FileMaker DDR SQLite database")
    diff_parser.add_argument(
        "--from",
        dest="from_snapshot",
        help="Snapshot to compare from (defaults to most recent)",
    )
    diff_parser.add_argument(
        "--to",
        dest="to_snapshot",
        help="Snapshot to compare to (defaults to current DB state)",
    )
    diff_parser.set_defaults(func=cmd_diff)

    # Report command
    report_parser = subparsers.add_parser("report", help="Generate a structured change report")
    report_parser.add_argument("db_path", help="Path to the FileMaker DDR SQLite database")
    report_parser.add_argument(
        "--from",
        dest="from_snapshot",
        help="Snapshot to compare from (defaults to most recent)",
    )
    report_parser.add_argument(
        "--format",
        dest="format",
        choices=["text", "json", "html"],
        default="text",
        help="Report format (default: text)",
    )
    report_parser.set_defaults(func=cmd_report)

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(0)

    args.func(args)


if __name__ == "__main__":
    main()
