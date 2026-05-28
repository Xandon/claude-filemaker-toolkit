#!/usr/bin/env python3
"""
FileMaker DDR Diagnostic Tool

Advanced diagnostic queries for FileMaker solutions: performance analysis,
impact assessment, and code quality checks.

Usage:
    python fm_diagnostics.py <db_path> <command> [args...]

Performance Commands:
    hotspots                   Scripts ranked by complexity (steps, depth, calls)
    trace <name|id>            Full call tree with cumulative step counts
    slow-patterns              Detect known performance anti-patterns

Impact Analysis Commands:
    impact <name>              What depends on this script/field/table/layout?
    orphans                    Scripts, fields, and layouts with no references

Code Quality Commands:
    health                     Overall solution health scorecard
    duplicates                 Find scripts with suspiciously similar structure
    no-error-handling          Scripts that use risky operations without error checks
    dead-code                  Scripts with disabled steps (incomplete refactoring)
    anti-patterns              Comprehensive anti-pattern scan across all scripts
"""

import sys
import sqlite3
import json
import re
from collections import defaultdict


def get_conn(db_path):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def find_script(conn, name_or_id):
    """Find a script by name or ID (partial, case-insensitive)."""
    c = conn.cursor()
    try:
        sid = int(name_or_id)
        c.execute("SELECT * FROM scripts WHERE script_id=?", (sid,))
        row = c.fetchone()
        if row:
            return row
    except ValueError:
        pass
    c.execute("SELECT * FROM scripts WHERE name=? COLLATE NOCASE", (name_or_id,))
    row = c.fetchone()
    if row:
        return row
    c.execute("SELECT * FROM scripts WHERE name LIKE ? COLLATE NOCASE",
              (f'%{name_or_id}%',))
    rows = c.fetchall()
    if len(rows) == 1:
        return rows[0]
    if len(rows) > 1:
        print(f"Multiple matches for '{name_or_id}':")
        for r in rows:
            print(f"  [{r['script_id']}] {r['name']}")
        return None
    print(f"Script not found: {name_or_id}")
    return None


# ============================================================
# PERFORMANCE COMMANDS
# ============================================================

def cmd_hotspots(conn, top_n=30):
    """Rank scripts by complexity — step count, call depth, layout switches, subscript calls."""
    c = conn.cursor()

    # Get all non-folder scripts with step counts
    c.execute("""
        SELECT s.script_id, s.name, s.step_count, s.is_hidden,
               (SELECT COUNT(*) FROM script_steps ss
                WHERE ss.script_id = s.script_id
                AND ss.step_name = 'Go to Layout') as layout_switches,
               (SELECT COUNT(*) FROM script_steps ss
                WHERE ss.script_id = s.script_id
                AND ss.step_name = 'Perform Script') as subscript_calls,
               (SELECT COUNT(*) FROM script_steps ss
                WHERE ss.script_id = s.script_id
                AND ss.enabled = 0) as disabled_steps,
               (SELECT COUNT(*) FROM script_steps ss
                WHERE ss.script_id = s.script_id
                AND ss.step_name = 'Perform Find') as find_ops,
               (SELECT COUNT(*) FROM script_references sr
                WHERE sr.target_script_id = s.script_id) as caller_count
        FROM scripts s
        WHERE s.step_count > 0 AND s.is_folder = 0
        ORDER BY s.step_count DESC
        LIMIT ?
    """, (top_n,))

    rows = c.fetchall()
    if not rows:
        print("No scripts found.")
        return

    print(f"\n{'Script Hotspots — Top {0} by Complexity'.format(top_n)}")
    print("=" * 110)
    print(f"{'Steps':>6} {'Layouts':>8} {'SubCalls':>9} {'Finds':>6} {'Dead':>5} {'Callers':>8}  Name")
    print("─" * 110)

    for r in rows:
        flags = ""
        if r['layout_switches'] > 5:
            flags += " ⚠ many layouts"
        if r['subscript_calls'] > 10:
            flags += " ⚠ deep calls"
        if r['disabled_steps'] > r['step_count'] * 0.2:
            flags += " ⚠ dead code"
        print(f"{r['step_count']:>6} {r['layout_switches']:>8} {r['subscript_calls']:>9} "
              f"{r['find_ops']:>6} {r['disabled_steps']:>5} {r['caller_count']:>8}  "
              f"{r['name']}{flags}")


def cmd_trace(conn, name_or_id, depth=0, visited=None, cumulative=None):
    """Trace the full call tree with cumulative step counts."""
    if visited is None:
        visited = set()
        cumulative = [0]
        print("\nCall Tree Trace")
        print("=" * 80)
        print(f"{'Depth':>5} {'Steps':>6} {'Cumul':>7}  Script")
        print("─" * 80)

    script = find_script(conn, name_or_id)
    if not script:
        return cumulative[0]

    sid = script['script_id']
    steps = script['step_count'] or 0

    if sid in visited:
        print(f"{'':>{5+depth*2}} {'':>6} {'':>7}  {'  '*depth}↻ {script['name']} (circular)")
        return cumulative[0]
    visited.add(sid)

    cumulative[0] += steps
    print(f"{depth:>5} {steps:>6} {cumulative[0]:>7}  {'  '*depth}{script['name']}")

    c = conn.cursor()
    c.execute("""SELECT DISTINCT target_script_id, target_script_name
                 FROM script_references WHERE source_type='script' AND source_id=?
                 ORDER BY target_script_name""", (sid,))

    for call in c.fetchall():
        cmd_trace(conn, str(call['target_script_id']), depth + 1, visited, cumulative)

    if depth == 0:
        print("─" * 80)
        print(f"Total cumulative steps in call tree: {cumulative[0]}")
    return cumulative[0]


def cmd_slow_patterns(conn):
    """Detect known FileMaker performance anti-patterns."""
    c = conn.cursor()
    print("\nPerformance Anti-Pattern Scan")
    print("=" * 90)
    issues = []

    # 1. Layout switches inside loops
    c.execute("""
        SELECT DISTINCT ss.script_id, ss.script_name
        FROM script_steps ss
        WHERE ss.step_name = 'Go to Layout'
        AND EXISTS (
            SELECT 1 FROM script_steps loop_start
            WHERE loop_start.script_id = ss.script_id
            AND loop_start.step_name = 'Loop'
            AND loop_start.step_index < ss.step_index
            AND EXISTS (
                SELECT 1 FROM script_steps loop_end
                WHERE loop_end.script_id = ss.script_id
                AND loop_end.step_name = 'End Loop'
                AND loop_end.step_index > ss.step_index
                AND loop_end.step_index > loop_start.step_index
            )
        )
    """)
    rows = c.fetchall()
    if rows:
        issues.append(("PERF-01", "Layout switch inside loop", "critical", rows,
                        "Go to Layout inside a Loop forces FileMaker to reload the layout context on every iteration. Move layout navigation outside the loop."))

    # 2. Replace Field Contents (operates on entire found set)
    c.execute("""
        SELECT DISTINCT ss.script_id, ss.script_name
        FROM script_steps ss
        WHERE ss.step_name LIKE '%Replace Field Contents%'
        AND ss.enabled = 1
    """)
    rows = c.fetchall()
    if rows:
        issues.append(("PERF-02", "Replace Field Contents used", "high", rows,
                        "Operates on the entire found set. On large tables this is slow and risky — consider looping with Set Field instead, or constrain the found set first."))

    # 3. Delete All Records
    c.execute("""
        SELECT DISTINCT ss.script_id, ss.script_name
        FROM script_steps ss
        WHERE ss.step_name LIKE '%Delete All Records%'
        AND ss.enabled = 1
    """)
    rows = c.fetchall()
    if rows:
        issues.append(("PERF-03", "Delete All Records used", "high", rows,
                        "Deletes every record in the found set. Ensure the found set is properly constrained and there's a safety guard (e.g., If [ Get(FoundCount) < threshold ])."))

    # 4. Perform Find inside a loop
    c.execute("""
        SELECT DISTINCT ss.script_id, ss.script_name
        FROM script_steps ss
        WHERE ss.step_name = 'Perform Find'
        AND EXISTS (
            SELECT 1 FROM script_steps loop_start
            WHERE loop_start.script_id = ss.script_id
            AND loop_start.step_name = 'Loop'
            AND loop_start.step_index < ss.step_index
            AND EXISTS (
                SELECT 1 FROM script_steps loop_end
                WHERE loop_end.script_id = ss.script_id
                AND loop_end.step_name = 'End Loop'
                AND loop_end.step_index > ss.step_index
            )
        )
    """)
    rows = c.fetchall()
    if rows:
        issues.append(("PERF-04", "Perform Find inside loop", "critical", rows,
                        "Find operations inside loops are extremely slow. Consider building a multi-request find, using GTRR, or restructuring to avoid repeated finds."))

    # 5. Perform Script inside a loop (potential n+1 pattern)
    c.execute("""
        SELECT ss.script_id, ss.script_name, COUNT(*) as call_count
        FROM script_steps ss
        WHERE ss.step_name = 'Perform Script'
        AND ss.enabled = 1
        AND EXISTS (
            SELECT 1 FROM script_steps loop_start
            WHERE loop_start.script_id = ss.script_id
            AND loop_start.step_name = 'Loop'
            AND loop_start.step_index < ss.step_index
            AND EXISTS (
                SELECT 1 FROM script_steps loop_end
                WHERE loop_end.script_id = ss.script_id
                AND loop_end.step_name = 'End Loop'
                AND loop_end.step_index > ss.step_index
            )
        )
        GROUP BY ss.script_id, ss.script_name
    """)
    rows = c.fetchall()
    if rows:
        issues.append(("PERF-05", "Perform Script inside loop (n+1 pattern)", "medium", rows,
                        "Subscript calls inside loops add overhead per iteration. If the subscript does layout switches, finds, or commits, this compounds dramatically. Consider batching."))

    # 6. Scripts with very deep call chains (> 5 levels)
    deep_scripts = []
    c.execute("SELECT script_id, name FROM scripts WHERE step_count > 0 AND is_folder = 0")
    all_scripts = c.fetchall()
    for s in all_scripts:
        depth = _measure_call_depth(conn, s['script_id'], set())
        if depth >= 5:
            deep_scripts.append((s['script_id'], s['name'], depth))
    if deep_scripts:
        deep_scripts.sort(key=lambda x: -x[2])
        issues.append(("PERF-06", f"Deep call chains (>= 5 levels)", "medium",
                        [{"script_id": d[0], "script_name": f"{d[1]} (depth: {d[2]})"} for d in deep_scripts[:15]],
                        "Deep call chains increase stack overhead and make debugging difficult. Consider flattening or using script parameters to reduce nesting."))

    # 7. Commit Records inside a loop
    c.execute("""
        SELECT DISTINCT ss.script_id, ss.script_name
        FROM script_steps ss
        WHERE (ss.step_name LIKE '%Commit%' OR ss.step_name LIKE '%commit%')
        AND ss.enabled = 1
        AND EXISTS (
            SELECT 1 FROM script_steps loop_start
            WHERE loop_start.script_id = ss.script_id
            AND loop_start.step_name = 'Loop'
            AND loop_start.step_index < ss.step_index
            AND EXISTS (
                SELECT 1 FROM script_steps loop_end
                WHERE loop_end.script_id = ss.script_id
                AND loop_end.step_name = 'End Loop'
                AND loop_end.step_index > ss.step_index
            )
        )
    """)
    rows = c.fetchall()
    if rows:
        issues.append(("PERF-07", "Commit Records inside loop", "medium", rows,
                        "Committing on each loop iteration forces a disk write and triggers auto-enter calcs each time. Consider committing once after the loop completes."))

    # Print results
    if not issues:
        print("\n  No performance anti-patterns detected.")
        return

    for code, title, severity, scripts, description in issues:
        sev_marker = {"critical": "!!!", "high": "!! ", "medium": "!  "}
        print(f"\n  {sev_marker.get(severity, '   ')} [{code}] {title}  ({severity})")
        print(f"      {description}")
        print(f"      Affected scripts ({len(scripts)}):")
        for s in scripts[:10]:
            name = s['script_name'] if isinstance(s, dict) else s['script_name']
            sid = s['script_id'] if isinstance(s, dict) else s['script_id']
            print(f"        [{sid}] {name}")
        if len(scripts) > 10:
            print(f"        ... and {len(scripts) - 10} more")

    print(f"\n{'─'*90}")
    by_sev = defaultdict(int)
    for _, _, sev, scripts, _ in issues:
        by_sev[sev] += len(scripts)
    print(f"  Total: {sum(by_sev.values())} script instances across {len(issues)} pattern types")
    for sev in ["critical", "high", "medium"]:
        if sev in by_sev:
            print(f"    {sev}: {by_sev[sev]} instances")


def _measure_call_depth(conn, script_id, visited, depth=0):
    """Measure the maximum call depth from a script."""
    if script_id in visited:
        return depth
    visited.add(script_id)
    c = conn.cursor()
    c.execute("""SELECT DISTINCT target_script_id FROM script_references
                 WHERE source_type='script' AND source_id=?""", (script_id,))
    max_depth = depth
    for row in c.fetchall():
        d = _measure_call_depth(conn, row[0], visited.copy(), depth + 1)
        if d > max_depth:
            max_depth = d
    return max_depth


# ============================================================
# IMPACT ANALYSIS COMMANDS
# ============================================================

def cmd_impact(conn, name):
    """Show everything that depends on a script, field, table, or layout."""
    c = conn.cursor()
    print(f"\nImpact Analysis for: {name}")
    print("=" * 80)
    found_anything = False

    # Check if it's a script
    c.execute("SELECT script_id, name FROM scripts WHERE name LIKE ? COLLATE NOCASE",
              (f'%{name}%',))
    scripts = c.fetchall()
    if scripts:
        found_anything = True
        for s in scripts:
            print(f"\n  Script: [{s['script_id']}] {s['name']}")
            # Who calls this script?
            c.execute("""SELECT source_type, source_id, source_name, context
                         FROM script_references WHERE target_script_id=?""", (s['script_id'],))
            refs = c.fetchall()
            if refs:
                print(f"    Called by ({len(refs)}):")
                for r in refs:
                    print(f"      {r['source_type']}: [{r['source_id']}] {r['source_name']}  ({r['context']})")
            else:
                print(f"    Called by: (nothing — orphan script)")

            # What does this script call?
            c.execute("""SELECT DISTINCT target_script_id, target_script_name
                         FROM script_references WHERE source_type='script' AND source_id=?""",
                      (s['script_id'],))
            calls = c.fetchall()
            if calls:
                print(f"    Calls ({len(calls)}):")
                for cl in calls:
                    print(f"      [{cl['target_script_id']}] {cl['target_script_name']}")

    # Check if it's a field
    c.execute("SELECT table_name, name, field_id FROM fields WHERE name LIKE ? COLLATE NOCASE",
              (f'%{name}%',))
    fields = c.fetchall()
    if fields:
        found_anything = True
        for f in fields:
            print(f"\n  Field: {f['table_name']}::{f['name']} (id:{f['field_id']})")
            # Find references in scripts
            c.execute("""SELECT DISTINCT script_id, script_name FROM script_steps
                         WHERE human_readable LIKE ? COLLATE NOCASE""",
                      (f'%{f["name"]}%',))
            step_refs = c.fetchall()
            if step_refs:
                print(f"    Used in scripts ({len(step_refs)}):")
                for sr in step_refs[:15]:
                    print(f"      [{sr['script_id']}] {sr['script_name']}")
                if len(step_refs) > 15:
                    print(f"      ... and {len(step_refs) - 15} more")

            # Find references in layouts
            c.execute("""SELECT DISTINCT l.layout_id, l.name FROM layout_references lr
                         JOIN layouts l ON lr.layout_id = l.layout_id
                         WHERE lr.field_name LIKE ? COLLATE NOCASE""",
                      (f'%{f["name"]}%',))
            layout_refs = c.fetchall()
            if layout_refs:
                print(f"    Placed on layouts ({len(layout_refs)}):")
                for lr in layout_refs[:10]:
                    print(f"      [{lr['layout_id']}] {lr['name']}")

            # Find references in calculations
            c.execute("""SELECT table_name, name FROM fields
                         WHERE calculation_text LIKE ? COLLATE NOCASE
                         AND name != ?""",
                      (f'%{f["name"]}%', f['name']))
            calc_refs = c.fetchall()
            if calc_refs:
                print(f"    Referenced in calculations ({len(calc_refs)}):")
                for cr in calc_refs[:10]:
                    print(f"      {cr['table_name']}::{cr['name']}")

    # Check if it's a table
    c.execute("SELECT table_id, name FROM tables_def WHERE name LIKE ? COLLATE NOCASE",
              (f'%{name}%',))
    tables = c.fetchall()
    if tables:
        found_anything = True
        for t in tables:
            print(f"\n  Table: {t['name']} (id:{t['table_id']})")
            # Relationships involving this table
            c.execute("""SELECT * FROM relationships
                         WHERE left_table LIKE ? OR right_table LIKE ?""",
                      (f'%{t["name"]}%', f'%{t["name"]}%'))
            rels = c.fetchall()
            if rels:
                print(f"    Relationships ({len(rels)}):")
                for r in rels:
                    print(f"      {r['left_table']}::{r['left_field']} → {r['right_table']}::{r['right_field']}")

            # Layouts for this table
            c.execute("SELECT layout_id, name FROM layouts WHERE table_occurrence LIKE ?",
                      (f'%{t["name"]}%',))
            layouts = c.fetchall()
            if layouts:
                print(f"    Layouts ({len(layouts)}):")
                for l in layouts:
                    print(f"      [{l['layout_id']}] {l['name']}")

    # Check if it's a layout
    c.execute("SELECT layout_id, name, table_occurrence FROM layouts WHERE name LIKE ? COLLATE NOCASE",
              (f'%{name}%',))
    layouts = c.fetchall()
    if layouts:
        found_anything = True
        for l in layouts:
            print(f"\n  Layout: [{l['layout_id']}] {l['name']} (TO: {l['table_occurrence']})")
            # Scripts that navigate to this layout
            c.execute("""SELECT DISTINCT script_id, script_name FROM script_steps
                         WHERE step_name = 'Go to Layout'
                         AND human_readable LIKE ? COLLATE NOCASE""",
                      (f'%{l["name"]}%',))
            nav_scripts = c.fetchall()
            if nav_scripts:
                print(f"    Scripts navigating here ({len(nav_scripts)}):")
                for ns in nav_scripts:
                    print(f"      [{ns['script_id']}] {ns['script_name']}")

    if not found_anything:
        print(f"\n  No scripts, fields, tables, or layouts match '{name}'.")


def cmd_orphans(conn):
    """Find scripts, fields, and layouts that nothing references."""
    c = conn.cursor()
    print("\nOrphan Analysis")
    print("=" * 80)

    # Orphan scripts — no callers, not folders
    c.execute("""
        SELECT s.script_id, s.name, s.step_count
        FROM scripts s
        WHERE s.is_folder = 0
        AND s.step_count > 0
        AND NOT EXISTS (
            SELECT 1 FROM script_references sr
            WHERE sr.target_script_id = s.script_id
        )
        ORDER BY s.step_count DESC
    """)
    orphan_scripts = c.fetchall()
    if orphan_scripts:
        print(f"\n  Orphan Scripts — never called by anything ({len(orphan_scripts)}):")
        print(f"  {'ID':>6} {'Steps':>6}  Name")
        print(f"  {'─'*70}")
        for s in orphan_scripts:
            print(f"  {s['script_id']:>6} {s['step_count']:>6}  {s['name']}")
    else:
        print("\n  Orphan Scripts: None found")

    # Orphan layouts — not referenced by any script
    c.execute("""
        SELECT l.layout_id, l.name, l.table_occurrence
        FROM layouts l
        WHERE NOT EXISTS (
            SELECT 1 FROM script_steps ss
            WHERE ss.human_readable LIKE '%' || l.name || '%'
            AND ss.step_name IN ('Go to Layout')
        )
        AND l.name NOT LIKE '%-%'
        ORDER BY l.name
    """)
    orphan_layouts = c.fetchall()
    if orphan_layouts:
        print(f"\n  Layouts never navigated to by scripts ({len(orphan_layouts)}):")
        print(f"  (Note: may be directly accessed by users or navigation buttons)")
        for l in orphan_layouts[:20]:
            print(f"    [{l['layout_id']}] {l['name']}  (TO: {l['table_occurrence']})")
        if len(orphan_layouts) > 20:
            print(f"    ... and {len(orphan_layouts) - 20} more")


# ============================================================
# CODE QUALITY COMMANDS
# ============================================================

def cmd_health(conn):
    """Generate an overall solution health scorecard."""
    c = conn.cursor()

    print("\nSolution Health Scorecard")
    print("=" * 80)

    # Basic stats
    c.execute("SELECT filename FROM files LIMIT 1")
    row = c.fetchone()
    print(f"\n  Solution: {row['filename'] if row else 'unknown'}")

    total_scripts = c.execute("SELECT COUNT(*) FROM scripts WHERE is_folder=0 AND step_count>0").fetchone()[0]
    total_steps = c.execute("SELECT COALESCE(SUM(step_count),0) FROM scripts WHERE is_folder=0").fetchone()[0]
    disabled_steps = c.execute("SELECT COUNT(*) FROM script_steps WHERE enabled=0").fetchone()[0]
    total_step_rows = c.execute("SELECT COUNT(*) FROM script_steps").fetchone()[0]

    print(f"  Scripts: {total_scripts}  |  Total steps: {total_steps}")
    print()

    # Metrics
    metrics = []

    # 1. Disabled step ratio
    if total_step_rows > 0:
        disabled_pct = disabled_steps / total_step_rows * 100
        grade = "A" if disabled_pct < 2 else "B" if disabled_pct < 5 else "C" if disabled_pct < 10 else "D"
        metrics.append(("Dead Code Ratio", f"{disabled_pct:.1f}% disabled ({disabled_steps}/{total_step_rows} steps)", grade))

    # 2. Orphan script ratio
    orphan_count = c.execute("""
        SELECT COUNT(*) FROM scripts s
        WHERE s.is_folder=0 AND s.step_count>0
        AND NOT EXISTS (SELECT 1 FROM script_references sr WHERE sr.target_script_id=s.script_id)
    """).fetchone()[0]
    if total_scripts > 0:
        orphan_pct = orphan_count / total_scripts * 100
        grade = "A" if orphan_pct < 10 else "B" if orphan_pct < 20 else "C" if orphan_pct < 35 else "D"
        metrics.append(("Orphan Scripts", f"{orphan_pct:.0f}% unreferenced ({orphan_count}/{total_scripts})", grade))

    # 3. Error handling coverage (scripts with Perform Find but no Get(LastError) check)
    scripts_with_find = c.execute("""
        SELECT COUNT(DISTINCT script_id) FROM script_steps
        WHERE step_name='Perform Find' AND enabled=1
    """).fetchone()[0]
    scripts_with_find_and_error = c.execute("""
        SELECT COUNT(DISTINCT ss1.script_id) FROM script_steps ss1
        WHERE ss1.step_name='Perform Find' AND ss1.enabled=1
        AND EXISTS (
            SELECT 1 FROM script_steps ss2
            WHERE ss2.script_id=ss1.script_id
            AND ss2.human_readable LIKE '%LastError%'
        )
    """).fetchone()[0]
    if scripts_with_find > 0:
        coverage = scripts_with_find_and_error / scripts_with_find * 100
        grade = "A" if coverage > 90 else "B" if coverage > 70 else "C" if coverage > 50 else "D"
        metrics.append(("Find Error Handling", f"{coverage:.0f}% of scripts with Perform Find check LastError ({scripts_with_find_and_error}/{scripts_with_find})", grade))

    # 4. Average script complexity
    c.execute("SELECT AVG(step_count) FROM scripts WHERE is_folder=0 AND step_count>0")
    avg_steps = c.fetchone()[0] or 0
    grade = "A" if avg_steps < 30 else "B" if avg_steps < 50 else "C" if avg_steps < 80 else "D"
    metrics.append(("Avg Script Size", f"{avg_steps:.0f} steps per script", grade))

    # 5. Large scripts (over 100 steps)
    large_count = c.execute("SELECT COUNT(*) FROM scripts WHERE step_count>100 AND is_folder=0").fetchone()[0]
    grade = "A" if large_count < 3 else "B" if large_count < 8 else "C" if large_count < 15 else "D"
    metrics.append(("Large Scripts (>100 steps)", f"{large_count} scripts", grade))

    # 6. Scripts with Set Error Capture but no Off
    c.execute("""
        SELECT COUNT(DISTINCT ss1.script_id) FROM script_steps ss1
        WHERE ss1.human_readable LIKE '%Error Capture%On%' AND ss1.enabled=1
        AND NOT EXISTS (
            SELECT 1 FROM script_steps ss2
            WHERE ss2.script_id=ss1.script_id
            AND ss2.human_readable LIKE '%Error Capture%Off%'
            AND ss2.enabled=1
        )
    """)
    error_leak_count = c.fetchone()[0]
    grade = "A" if error_leak_count == 0 else "B" if error_leak_count < 3 else "C" if error_leak_count < 8 else "D"
    metrics.append(("Error Capture Leaks", f"{error_leak_count} scripts turn On but never Off", grade))

    # Print scorecard
    overall_grades = [m[2] for m in metrics]
    grade_values = {"A": 4, "B": 3, "C": 2, "D": 1}
    overall_gpa = sum(grade_values[g] for g in overall_grades) / len(overall_grades) if overall_grades else 0
    overall = "A" if overall_gpa >= 3.5 else "B" if overall_gpa >= 2.5 else "C" if overall_gpa >= 1.5 else "D"

    print(f"  {'Metric':<35} {'Grade':>5}  Detail")
    print(f"  {'─'*75}")
    for name, detail, grade in metrics:
        marker = "  " if grade in ("A", "B") else "⚠ " if grade == "C" else "!! "
        print(f"  {marker}{name:<33} [{grade}]    {detail}")

    print(f"\n  {'─'*75}")
    print(f"  Overall Grade: [{overall}]  (GPA: {overall_gpa:.1f}/4.0)")


def cmd_duplicates(conn, threshold=0.80):
    """Find scripts with suspiciously similar structure."""
    c = conn.cursor()
    print(f"\nDuplicate Script Detection (threshold: {threshold*100:.0f}%)")
    print("=" * 80)

    # Get scripts with their step signatures (sequence of step names)
    c.execute("""
        SELECT s.script_id, s.name, s.step_count,
               GROUP_CONCAT(ss.step_name, '|') as step_signature
        FROM scripts s
        JOIN script_steps ss ON s.script_id = ss.script_id
        WHERE s.is_folder = 0 AND s.step_count > 10 AND ss.enabled = 1
        GROUP BY s.script_id
        ORDER BY s.step_count DESC
    """)

    scripts = c.fetchall()
    pairs = []

    for i, s1 in enumerate(scripts):
        for s2 in scripts[i+1:]:
            # Quick filter: step counts should be within 20% of each other
            if s1['step_count'] and s2['step_count']:
                ratio = min(s1['step_count'], s2['step_count']) / max(s1['step_count'], s2['step_count'])
                if ratio < 0.7:
                    continue

            # Compare step signatures
            sig1 = s1['step_signature'].split('|') if s1['step_signature'] else []
            sig2 = s2['step_signature'].split('|') if s2['step_signature'] else []
            similarity = _sequence_similarity(sig1, sig2)
            if similarity >= threshold:
                pairs.append((s1, s2, similarity))

    pairs.sort(key=lambda x: -x[2])

    if not pairs:
        print("\n  No duplicate scripts detected.")
        return

    print(f"\n  Found {len(pairs)} duplicate pair(s):\n")
    for s1, s2, sim in pairs[:15]:
        print(f"  {sim*100:.0f}% similar:")
        print(f"    [{s1['script_id']}] {s1['name']} ({s1['step_count']} steps)")
        print(f"    [{s2['script_id']}] {s2['name']} ({s2['step_count']} steps)")
        print()

    if len(pairs) > 15:
        print(f"  ... and {len(pairs) - 15} more pairs")


def _sequence_similarity(seq1, seq2):
    """Fast similarity check using shared subsequence ratio."""
    if not seq1 or not seq2:
        return 0.0
    # Use a simple approach: count matching elements at same positions
    min_len = min(len(seq1), len(seq2))
    max_len = max(len(seq1), len(seq2))
    matches = sum(1 for i in range(min_len) if seq1[i] == seq2[i])
    return matches / max_len if max_len > 0 else 0.0


def cmd_no_error_handling(conn):
    """Find scripts that use risky operations without error handling."""
    c = conn.cursor()
    print("\nScripts Missing Error Handling")
    print("=" * 80)

    risky_ops = [
        ("Perform Find", "LastError", "Perform Find with no Get(LastError) check"),
        ("Import Records", "LastError", "Import Records with no error check"),
        ("Delete Record/Request", "LastError", "Delete Record with no error check"),
        ("Delete All Records", "LastError", "Delete All Records with no error check"),
    ]

    for op_name, check_term, description in risky_ops:
        c.execute(f"""
            SELECT DISTINCT ss.script_id, ss.script_name
            FROM script_steps ss
            WHERE ss.step_name LIKE ? AND ss.enabled = 1
            AND NOT EXISTS (
                SELECT 1 FROM script_steps ss2
                WHERE ss2.script_id = ss.script_id
                AND ss2.human_readable LIKE ?
            )
        """, (f'%{op_name}%', f'%{check_term}%'))
        rows = c.fetchall()
        if rows:
            print(f"\n  {description} ({len(rows)} scripts):")
            for r in rows[:10]:
                print(f"    [{r['script_id']}] {r['script_name']}")
            if len(rows) > 10:
                print(f"    ... and {len(rows) - 10} more")


def cmd_dead_code(conn):
    """Find scripts with significant disabled steps."""
    c = conn.cursor()
    print("\nDead Code Analysis")
    print("=" * 80)

    c.execute("""
        SELECT s.script_id, s.name, s.step_count,
               (SELECT COUNT(*) FROM script_steps ss
                WHERE ss.script_id = s.script_id AND ss.enabled = 0) as disabled
        FROM scripts s
        WHERE s.is_folder = 0 AND s.step_count > 5
        HAVING disabled > 0
        ORDER BY disabled DESC
    """)
    rows = c.fetchall()
    if not rows:
        print("\n  No scripts with disabled steps found.")
        return

    total_disabled = sum(r['disabled'] for r in rows)
    print(f"\n  {len(rows)} scripts with disabled steps ({total_disabled} total disabled steps)")
    print(f"\n  {'ID':>6} {'Total':>6} {'Dead':>5} {'%':>5}  Script Name")
    print(f"  {'─'*75}")
    for r in rows[:25]:
        pct = r['disabled'] / r['step_count'] * 100 if r['step_count'] else 0
        flag = " ← majority disabled" if pct > 50 else ""
        print(f"  {r['script_id']:>6} {r['step_count']:>6} {r['disabled']:>5} {pct:>4.0f}%  {r['name']}{flag}")
    if len(rows) > 25:
        print(f"\n  ... and {len(rows) - 25} more scripts")


def cmd_anti_patterns(conn):
    """Comprehensive anti-pattern scan combining performance and quality checks."""
    print("\nComprehensive Anti-Pattern Report")
    print("=" * 90)
    cmd_slow_patterns(conn)
    print()
    cmd_no_error_handling(conn)
    print()
    cmd_dead_code(conn)


# ============================================================
# MAIN
# ============================================================

def main():
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)

    db_path = sys.argv[1]
    command = sys.argv[2]
    args = sys.argv[3:]

    conn = get_conn(db_path)

    try:
        if command == 'hotspots':
            top_n = int(args[0]) if args else 30
            cmd_hotspots(conn, top_n)
        elif command == 'trace':
            if not args:
                print("Usage: trace <script_name_or_id>")
                sys.exit(1)
            cmd_trace(conn, ' '.join(args))
        elif command == 'slow-patterns':
            cmd_slow_patterns(conn)
        elif command == 'impact':
            if not args:
                print("Usage: impact <name>")
                sys.exit(1)
            cmd_impact(conn, ' '.join(args))
        elif command == 'orphans':
            cmd_orphans(conn)
        elif command == 'health':
            cmd_health(conn)
        elif command == 'duplicates':
            threshold = float(args[0]) if args else 0.80
            cmd_duplicates(conn, threshold)
        elif command == 'no-error-handling':
            cmd_no_error_handling(conn)
        elif command == 'dead-code':
            cmd_dead_code(conn)
        elif command == 'anti-patterns':
            cmd_anti_patterns(conn)
        else:
            print(f"Unknown command: {command}")
            print(__doc__)
    finally:
        conn.close()


if __name__ == '__main__':
    main()
