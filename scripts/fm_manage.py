#!/usr/bin/env python3
"""
FileMaker Solution Manager
==========================
Wrapper script for managing multiple FileMaker DDR XML solutions.
Handles indexing, querying, reviewing, and organizing solution files
within the solutions/ directory structure.

Usage:
    python fm_manage.py list                         # List all indexed solutions
    python fm_manage.py index <xml_file> [--name X]  # Index a new XML export
    python fm_manage.py query <solution> <command>    # Query a solution's database
    python fm_manage.py review <solution> <json>      # Generate a code review HTML
    python fm_manage.py extract <solution> <script>   # Extract script XML for MBS
    python fm_manage.py diagnose <solution> <cmd>     # Run diagnostics (health, hotspots, complexity, etc.)
    python fm_manage.py graph <solution>              # Generate relationship graph HTML
    python fm_manage.py diff <solution> <old.db> <cmd> # Compare two DB versions
    python fm_manage.py bulk-review <solution>        # Auto-generate review from diagnostics
    python fm_manage.py summary <solution>            # Quick summary of a solution

Directory structure:
    solutions/
    ├── LAYER/
    │   ├── LAYER.xml          # Original DDR XML export
    │   ├── LAYER.db           # Indexed SQLite database (or in DB_CACHE_DIR)
    │   ├── reviews/           # Code review JSON definitions
    │   └── output/            # Generated HTML reviews, extracted XML, reports
    └── HaverSS/
        ├── HaverSS.xml
        ├── HaverSS.db
        ├── reviews/
        └── output/

Note: SQLite databases may be stored in a cache directory outside the
mounted filesystem if the mount doesn't support SQLite's locking.
The manager handles this transparently.
"""

import argparse
import os
import sys
import subprocess
import sqlite3
import shutil
from pathlib import Path
from datetime import datetime

# Resolve paths:
#   SCRIPT_DIR   — where fm_*.py live (inside the plugin)
#   PROJECT_DIR  — the current working directory (user's FM project folder)
#   SOLUTIONS_DIR — <project>/solutions  (per-project, matches current layout)
#   TOOLKIT_DIR  — where the other fm_*.py scripts live (same as SCRIPT_DIR in plugin)
SCRIPT_DIR = Path(__file__).resolve().parent
TOOLKIT_DIR = SCRIPT_DIR


def _resolve_project_dir():
    """Resolve the project directory with multiple fallback strategies.

    Priority:
      1. --project-dir CLI argument (handled in main(), sets FM_PROJECT_DIR)
      2. FM_PROJECT_DIR environment variable
      3. Walk upward from cwd looking for a solutions/ directory
      4. Walk upward from cwd looking for a .fm_project marker file
      5. Fall back to cwd
    """
    # Check env var first
    env_dir = os.environ.get("FM_PROJECT_DIR")
    if env_dir:
        return Path(env_dir).resolve()

    # Walk upward looking for solutions/ or .fm_project
    cwd = Path.cwd().resolve()
    check = cwd
    for _ in range(10):  # max 10 levels up
        if (check / "solutions").is_dir():
            return check
        if (check / ".fm_project").exists():
            return check
        parent = check.parent
        if parent == check:
            break
        check = parent

    return cwd


PROJECT_DIR = _resolve_project_dir()
SOLUTIONS_DIR = PROJECT_DIR / "solutions"

# SQLite DB cache: mounted Cowork filesystems don't always support SQLite locking,
# so we fall back to a writable cache. Order of preference:
#   1. FM_DB_CACHE environment variable (explicit override)
#   2. <project>/.fm_db_cache  (per-project, local)
#   3. ~/.cache/filemaker-toolkit/db_cache  (user-level fallback)
_env_cache = os.environ.get("FM_DB_CACHE")
if _env_cache:
    DB_CACHE_DIR = Path(_env_cache).resolve()
else:
    _local_cache = PROJECT_DIR / ".fm_db_cache"
    try:
        _local_cache.mkdir(parents=True, exist_ok=True)
        # Quick write test
        _probe = _local_cache / ".probe"
        _probe.touch()
        _probe.unlink()
        DB_CACHE_DIR = _local_cache
    except Exception:
        DB_CACHE_DIR = Path.home() / ".cache" / "filemaker-toolkit" / "db_cache"


def _ensure_db_cache():
    """Create the DB cache directory if needed."""
    DB_CACHE_DIR.mkdir(parents=True, exist_ok=True)


def _find_db(sol_name):
    """Find the .db file for a solution — checks solution dir first, then cache."""
    # Check solution directory
    sol_dir = SOLUTIONS_DIR / sol_name
    for db in sol_dir.glob("*.db"):
        # Verify it's actually readable by SQLite
        try:
            conn = sqlite3.connect(str(db))
            conn.execute("SELECT COUNT(*) FROM scripts")
            conn.close()
            return db
        except Exception:
            pass
    # Check cache directory
    cached = DB_CACHE_DIR / f"{sol_name}.db"
    if cached.exists():
        try:
            conn = sqlite3.connect(str(cached))
            conn.execute("SELECT COUNT(*) FROM scripts")
            conn.close()
            return cached
        except Exception:
            pass
    return None

FM_PARSER = TOOLKIT_DIR / "fm_parser.py"
FM_QUERY = TOOLKIT_DIR / "fm_query.py"
FM_XML_GEN = TOOLKIT_DIR / "fm_xml_gen.py"
FM_REVIEW_GEN = TOOLKIT_DIR / "fm_review_gen.py"
FM_DIAGNOSTICS = TOOLKIT_DIR / "fm_diagnostics.py"
FM_DIFF = TOOLKIT_DIR / "fm_diff.py"
FM_GRAPH = TOOLKIT_DIR / "fm_graph.py"


def get_solutions():
    """Discover all solution directories, finding DBs in solution dir or cache."""
    solutions = {}
    if not SOLUTIONS_DIR.exists():
        return solutions
    for entry in sorted(SOLUTIONS_DIR.iterdir()):
        if entry.is_dir():
            xml_files = list(entry.glob("*.xml"))
            db = _find_db(entry.name)
            xml = xml_files[0] if xml_files else None
            if db:
                # Get stats from the database
                try:
                    conn = sqlite3.connect(str(db))
                    c = conn.cursor()
                    stats = {}
                    for table_name in ["tables_def", "fields", "scripts", "script_steps",
                                       "layouts", "relationships"]:
                        try:
                            c.execute(f"SELECT COUNT(*) FROM {table_name}")
                            stats[table_name] = c.fetchone()[0]
                        except sqlite3.OperationalError:
                            stats[table_name] = 0
                    # Get source file info
                    source_file = "unknown"
                    indexed_at = "unknown"
                    try:
                        c.execute("SELECT filename, indexed_at FROM files LIMIT 1")
                        row = c.fetchone()
                        if row:
                            source_file = row[0]
                            indexed_at = row[1]
                    except sqlite3.OperationalError:
                        pass
                    conn.close()
                    solutions[entry.name] = {
                        "dir": entry,
                        "db": db,
                        "xml": xml,
                        "source_file": source_file,
                        "indexed_at": indexed_at,
                        "tables": stats.get("tables_def", 0),
                        "fields": stats.get("fields", 0),
                        "scripts": stats.get("scripts", 0),
                        "steps": stats.get("script_steps", 0),
                        "layouts": stats.get("layouts", 0),
                        "relationships": stats.get("relationships", 0),
                    }
                except Exception as e:
                    solutions[entry.name] = {
                        "dir": entry, "db": db, "xml": xml,
                        "error": str(e)
                    }
            elif xml_files:
                # Has XML but not yet indexed
                solutions[entry.name] = {
                    "dir": entry, "db": None,
                    "xml": xml_files[0], "indexed": False
                }
    return solutions


def resolve_solution(name):
    """Find a solution by name (case-insensitive partial match)."""
    solutions = get_solutions()
    # Exact match first
    if name in solutions:
        return name, solutions[name]
    # Case-insensitive match
    for sname, sdata in solutions.items():
        if sname.lower() == name.lower():
            return sname, sdata
    # Partial match
    matches = [(sname, sdata) for sname, sdata in solutions.items()
                if name.lower() in sname.lower()]
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        print(f"Ambiguous solution name '{name}'. Matches: {', '.join(m[0] for m in matches)}")
        sys.exit(1)
    print(f"Solution '{name}' not found. Available: {', '.join(solutions.keys()) or '(none)'}")
    sys.exit(1)


def cmd_list(args):
    """List all indexed solutions."""
    solutions = get_solutions()
    if not solutions:
        print("No solutions found in solutions/ directory.")
        print(f"Use: python {sys.argv[0]} index <xml_file> to add one.")
        return

    print(f"{'Solution':<20} {'Tables':>7} {'Fields':>7} {'Scripts':>8} {'Steps':>8} {'Layouts':>8} {'Rels':>6}  Source")
    print("─" * 105)
    for name, data in solutions.items():
        if "error" in data:
            print(f"{name:<20} (error reading database: {data['error']})")
        elif data.get("db") is None:
            print(f"{name:<20} (not indexed — XML present, run: python {sys.argv[0]} index solutions/{name}/*.xml)")
        else:
            print(f"{name:<20} {data['tables']:>7} {data['fields']:>7} {data['scripts']:>8} "
                  f"{data['steps']:>8} {data['layouts']:>8} {data['relationships']:>6}  "
                  f"{data['source_file']}")
    print()
    print(f"Solutions directory: {SOLUTIONS_DIR}")


def cmd_index(args):
    """Index a new XML file into a solution directory."""
    xml_path = Path(args.xml_file).resolve()
    if not xml_path.exists():
        print(f"XML file not found: {xml_path}")
        sys.exit(1)

    # Determine solution name
    if args.name:
        sol_name = args.name
    else:
        sol_name = xml_path.stem  # e.g., "HaverSS" from "HaverSS.xml"

    sol_dir = SOLUTIONS_DIR / sol_name
    sol_dir.mkdir(parents=True, exist_ok=True)
    (sol_dir / "reviews").mkdir(exist_ok=True)
    (sol_dir / "output").mkdir(exist_ok=True)

    # Copy XML to solution directory if not already there
    target_xml = sol_dir / xml_path.name
    if xml_path != target_xml and not target_xml.exists():
        print(f"Copying {xml_path.name} to {sol_dir}/...")
        shutil.copy2(str(xml_path), str(target_xml))

    # Index into a writable location first, then try to place in solution dir.
    # SQLite needs a filesystem that supports its locking — mounted dirs often don't.
    db_name = f"{sol_name}.db"
    _ensure_db_cache()
    temp_db = DB_CACHE_DIR / db_name

    # Remove stale temp DB if it exists (parser may append to existing)
    if temp_db.exists():
        temp_db.unlink()

    print(f"Indexing {xml_path.name} → {db_name}...")
    result = subprocess.run(
        [sys.executable, str(FM_PARSER), "index", str(target_xml), "--db", str(temp_db)],
        capture_output=True, text=True
    )
    print(result.stdout)
    if result.returncode != 0:
        print(result.stderr)
        sys.exit(1)

    # Verify the cache copy is valid before doing anything else
    if not temp_db.exists() or temp_db.stat().st_size == 0:
        print(f"ERROR: Indexer did not produce a valid database at {temp_db}")
        sys.exit(1)

    try:
        conn = sqlite3.connect(str(temp_db))
        conn.execute("SELECT COUNT(*) FROM scripts")
        conn.close()
    except Exception as e:
        print(f"ERROR: Cache database not readable: {e}")
        sys.exit(1)

    # Try to copy to the solution directory as a convenience;
    # keep the cache copy as the PRIMARY (it's on a writable FS).
    target_db = sol_dir / db_name
    sol_dir_works = False
    try:
        shutil.copy2(str(temp_db), str(target_db))
        # Verify the copy is readable by SQLite
        conn = sqlite3.connect(str(target_db))
        conn.execute("SELECT COUNT(*) FROM scripts")
        conn.close()
        sol_dir_works = True
    except Exception:
        pass

    # Report locations — never delete the cache copy
    if sol_dir_works:
        print(f"Database saved to: {target_db}")
        print(f"Database cached at: {temp_db}")
    else:
        print(f"Database saved to: {temp_db}")
        print(f"  (solution dir copy skipped — mount FS doesn't support SQLite)")

    # Write a .fm_project marker so future queries can find this project
    marker = PROJECT_DIR / ".fm_project"
    if not marker.exists():
        try:
            marker.write_text(f"# FileMaker Toolkit project marker\n# Created: {datetime.now().isoformat()}\n")
        except Exception:
            pass

    print(f"\nSolution '{sol_name}' is ready. Query it with:")
    print(f"  python {sys.argv[0]} query {sol_name} summary")
    print(f"  python {sys.argv[0]} query {sol_name} scripts")


def cmd_query(args):
    """Run a query against a solution's database."""
    sol_name, sol_data = resolve_solution(args.solution)
    if sol_data.get("db") is None:
        print(f"Solution '{sol_name}' is not indexed yet.")
        sys.exit(1)

    cmd = [sys.executable, str(FM_QUERY), str(sol_data["db"]), args.command] + args.extra
    result = subprocess.run(cmd, capture_output=False)
    sys.exit(result.returncode)


def cmd_review(args):
    """Generate a code review HTML from a review JSON definition."""
    sol_name, sol_data = resolve_solution(args.solution)
    if sol_data.get("db") is None:
        print(f"Solution '{sol_name}' is not indexed yet.")
        sys.exit(1)

    # Find the review JSON — check solution's reviews/ dir, then as a direct path
    review_path = Path(args.review_json)
    if not review_path.exists():
        # Try in the solution's reviews directory
        candidate = sol_data["dir"] / "reviews" / args.review_json
        if candidate.exists():
            review_path = candidate
        else:
            print(f"Review JSON not found: {args.review_json}")
            print(f"  Also checked: {candidate}")
            sys.exit(1)

    # Output goes to the solution's output directory
    if args.output:
        output_path = Path(args.output)
    else:
        stem = review_path.stem
        output_path = sol_data["dir"] / "output" / f"{stem}.html"

    cmd = [sys.executable, str(FM_REVIEW_GEN), "review", str(sol_data["db"]),
           str(review_path), "--output", str(output_path)]
    if args.template:
        cmd.extend(["--template", args.template])

    print(f"Generating review: {review_path.name} → {output_path}")
    result = subprocess.run(cmd, capture_output=False)
    if result.returncode == 0:
        print(f"\nReview saved to: {output_path}")
    sys.exit(result.returncode)


def cmd_extract(args):
    """Extract a script as XML for MBS plugin paste-back."""
    sol_name, sol_data = resolve_solution(args.solution)
    if sol_data.get("db") is None:
        print(f"Solution '{sol_name}' is not indexed yet.")
        sys.exit(1)

    # Sanitize script name for filename
    safe_name = args.script.replace(" ", "_").replace("/", "_")
    if args.output:
        output_path = args.output
    else:
        output_path = str(sol_data["dir"] / "output" / f"{safe_name}_extracted.xml")

    cmd = [sys.executable, str(FM_XML_GEN), "extract", str(sol_data["db"]),
           args.script, "--output", output_path]
    result = subprocess.run(cmd, capture_output=False)
    if result.returncode == 0:
        print(f"\nExtracted to: {output_path}")
    sys.exit(result.returncode)


def cmd_diagnose(args):
    """Run a diagnostic command against a solution."""
    sol_name, sol_data = resolve_solution(args.solution)
    if sol_data.get("db") is None:
        print(f"Solution '{sol_name}' is not indexed yet.")
        sys.exit(1)

    cmd = [sys.executable, str(FM_DIAGNOSTICS), str(sol_data["db"]),
           args.diag_command] + args.extra
    result = subprocess.run(cmd, capture_output=False)
    sys.exit(result.returncode)


def cmd_summary(args):
    """Show a detailed summary of a solution."""
    sol_name, sol_data = resolve_solution(args.solution)
    if sol_data.get("db") is None:
        print(f"Solution '{sol_name}' is not indexed yet.")
        sys.exit(1)

    # Use fm_query summary command
    cmd = [sys.executable, str(FM_QUERY), str(sol_data["db"]), "summary"]
    result = subprocess.run(cmd, capture_output=False)

    # Also list reviews and outputs
    reviews_dir = sol_data["dir"] / "reviews"
    output_dir = sol_data["dir"] / "output"

    review_files = list(reviews_dir.glob("*.json")) if reviews_dir.exists() else []
    output_files = list(output_dir.iterdir()) if output_dir.exists() else []

    if review_files:
        print(f"\nReview definitions ({len(review_files)}):")
        for f in review_files:
            print(f"  {f.name}")

    if output_files:
        print(f"\nGenerated outputs ({len(output_files)}):")
        for f in output_files:
            size = f.stat().st_size
            if size > 1_000_000:
                size_str = f"{size/1_000_000:.1f} MB"
            elif size > 1_000:
                size_str = f"{size/1_000:.1f} KB"
            else:
                size_str = f"{size} B"
            print(f"  {f.name:<40} {size_str:>10}")

    sys.exit(result.returncode)


def cmd_graph(args):
    """Generate an interactive relationship graph HTML."""
    sol_name, sol_data = resolve_solution(args.solution)
    if sol_data.get("db") is None:
        print(f"Solution '{sol_name}' is not indexed yet.")
        sys.exit(1)

    if args.output:
        output_path = Path(args.output)
    else:
        output_path = sol_data["dir"] / "output" / f"{sol_name}_graph.html"

    cmd = [sys.executable, str(FM_GRAPH), str(sol_data["db"]),
           "--output", str(output_path)]
    if args.focus:
        cmd.extend(["--focus", args.focus])
    if args.depth:
        cmd.extend(["--depth", str(args.depth)])

    print(f"Generating relationship graph → {output_path}")
    result = subprocess.run(cmd, capture_output=False)
    if result.returncode == 0:
        print(f"\nGraph saved to: {output_path}")
    sys.exit(result.returncode)


def cmd_diff(args):
    """Compare two versions of a solution using fm_diff."""
    sol_name, sol_data = resolve_solution(args.solution)
    if sol_data.get("db") is None:
        print(f"Solution '{sol_name}' is not indexed yet.")
        sys.exit(1)

    old_db = Path(args.old_db)
    if not old_db.exists():
        # Try in the DB cache
        cached = DB_CACHE_DIR / args.old_db
        if cached.exists():
            old_db = cached
        else:
            print(f"Old database not found: {args.old_db}")
            sys.exit(1)

    cmd = [sys.executable, str(FM_DIFF), str(old_db), str(sol_data["db"]),
           args.diff_command] + args.extra
    result = subprocess.run(cmd, capture_output=False)
    sys.exit(result.returncode)


def cmd_bulk_review(args):
    """Generate a bulk code review using auto-detection."""
    sol_name, sol_data = resolve_solution(args.solution)
    if sol_data.get("db") is None:
        print(f"Solution '{sol_name}' is not indexed yet.")
        sys.exit(1)

    if args.output:
        output_path = Path(args.output)
    else:
        output_path = sol_data["dir"] / "output" / f"{sol_name}_bulk_review.html"

    cmd = [sys.executable, str(FM_REVIEW_GEN), "bulk", str(sol_data["db"]),
           "--output", str(output_path)]
    if args.filter:
        cmd.extend(["--filter", args.filter])
    if args.min_steps:
        cmd.extend(["--min-steps", str(args.min_steps)])
    if args.checks:
        cmd.extend(["--checks", args.checks])

    print(f"Generating bulk review → {output_path}")
    result = subprocess.run(cmd, capture_output=False)
    if result.returncode == 0:
        print(f"\nBulk review saved to: {output_path}")
    sys.exit(result.returncode)


def main():
    parser = argparse.ArgumentParser(
        description="FileMaker Solution Manager — manage multiple DDR XML solutions",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
  Global options:
    --project-dir PATH   Set the project directory (default: auto-detect)
Examples:
  python fm_manage.py list
  python fm_manage.py index NewSolution.xml
  python fm_manage.py index NewSolution.xml --name CustomName
  python fm_manage.py query LAYER scripts
  python fm_manage.py query HaverSS script "My Script Name"
  python fm_manage.py query LAYER search "Import"
  python fm_manage.py summary HaverSS
  python fm_manage.py review LAYER review_mold_scripts.json
  python fm_manage.py extract HaverSS "Script Name"
  python fm_manage.py diagnose HaverSS health
  python fm_manage.py diagnose HaverSS hotspots
  python fm_manage.py diagnose HaverSS trace "Script Name"
  python fm_manage.py diagnose HaverSS slow-patterns
  python fm_manage.py diagnose HaverSS impact "Shopify_Orders"
  python fm_manage.py diagnose HaverSS orphans
  python fm_manage.py diagnose HaverSS anti-patterns
  python fm_manage.py diagnose HaverSS complexity "Script Name"
  python fm_manage.py diagnose HaverSS complexity-report
  python fm_manage.py diagnose HaverSS complexity-html --output complexity.html
  python fm_manage.py graph ILCrop --focus "Samples"
  python fm_manage.py diff ILCrop old_ILCrop.db diff-summary
  python fm_manage.py bulk-review ILCrop --min-steps 20 --checks no-error-handling,slow-patterns
        """
    )
    parser.add_argument("--project-dir", help="Project directory containing solutions/ (default: auto-detect)")
    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # list
    sub_list = subparsers.add_parser("list", aliases=["ls"],
                                      help="List all indexed solutions")
    sub_list.set_defaults(func=cmd_list)

    # index
    sub_index = subparsers.add_parser("index",
                                       help="Index a new FileMaker DDR XML export")
    sub_index.add_argument("xml_file", help="Path to the XML file")
    sub_index.add_argument("--name", help="Solution name (default: XML filename stem)")
    sub_index.set_defaults(func=cmd_index)

    # query
    sub_query = subparsers.add_parser("query", aliases=["q"],
                                       help="Query a solution's indexed database")
    sub_query.add_argument("solution", help="Solution name (partial match OK)")
    sub_query.add_argument("command", help="fm_query command (script, scripts, tables, search, etc.)")
    sub_query.add_argument("extra", nargs="*", help="Additional arguments for the query command")
    sub_query.set_defaults(func=cmd_query)

    # review
    sub_review = subparsers.add_parser("review",
                                        help="Generate a code review HTML report")
    sub_review.add_argument("solution", help="Solution name")
    sub_review.add_argument("review_json", help="Review JSON file (name or path)")
    sub_review.add_argument("--output", "-o", help="Output HTML path (default: output/<name>.html)")
    sub_review.add_argument("--template", "-t", help="Custom HTML template path")
    sub_review.set_defaults(func=cmd_review)

    # extract
    sub_extract = subparsers.add_parser("extract",
                                         help="Extract script XML for MBS paste-back")
    sub_extract.add_argument("solution", help="Solution name")
    sub_extract.add_argument("script", help="Script name or ID")
    sub_extract.add_argument("--output", "-o", help="Output XML path")
    sub_extract.set_defaults(func=cmd_extract)

    # diagnose
    sub_diag = subparsers.add_parser("diagnose", aliases=["diag", "dx"],
                                      help="Run diagnostic analysis (health, hotspots, slow-patterns, etc.)")
    sub_diag.add_argument("solution", help="Solution name (partial match OK)")
    sub_diag.add_argument("diag_command", help="Diagnostic command: health, hotspots, trace, slow-patterns, impact, orphans, duplicates, no-error-handling, dead-code, anti-patterns, complexity, complexity-report, complexity-html")
    sub_diag.add_argument("extra", nargs="*", help="Additional arguments")
    sub_diag.set_defaults(func=cmd_diagnose)

    # graph
    sub_graph = subparsers.add_parser("graph",
                                       help="Generate interactive relationship graph HTML")
    sub_graph.add_argument("solution", help="Solution name")
    sub_graph.add_argument("--output", "-o", help="Output HTML path")
    sub_graph.add_argument("--focus", "-f", help="Center on a specific table occurrence")
    sub_graph.add_argument("--depth", "-d", type=int, help="Hops from focus TO (default: all)")
    sub_graph.set_defaults(func=cmd_graph)

    # diff
    sub_diff = subparsers.add_parser("diff",
                                      help="Compare two versions of a solution")
    sub_diff.add_argument("solution", help="Solution name (current/new version)")
    sub_diff.add_argument("old_db", help="Path to old version's .db file")
    sub_diff.add_argument("diff_command", help="diff-summary, diff-scripts, diff-script, diff-fields, diff-html")
    sub_diff.add_argument("extra", nargs="*", help="Additional arguments (e.g., script name)")
    sub_diff.set_defaults(func=cmd_diff)

    # bulk-review
    sub_bulk = subparsers.add_parser("bulk-review", aliases=["bulk"],
                                      help="Auto-generate code review from diagnostics")
    sub_bulk.add_argument("solution", help="Solution name")
    sub_bulk.add_argument("--output", "-o", help="Output HTML path")
    sub_bulk.add_argument("--filter", "-f", help="Script folder path pattern (e.g., 'Admin/*')")
    sub_bulk.add_argument("--min-steps", type=int, help="Minimum step count threshold")
    sub_bulk.add_argument("--checks", "-c", help="Comma-separated checks: no-error-handling,slow-patterns,dead-code")
    sub_bulk.set_defaults(func=cmd_bulk_review)

    # summary
    sub_summary = subparsers.add_parser("summary", aliases=["info"],
                                         help="Show detailed summary of a solution")
    sub_summary.add_argument("solution", help="Solution name")
    sub_summary.set_defaults(func=cmd_summary)

    args = parser.parse_args()

    # Apply --project-dir override before any command runs
    if args.project_dir:
        global PROJECT_DIR, SOLUTIONS_DIR, DB_CACHE_DIR
        PROJECT_DIR = Path(args.project_dir).resolve()
        SOLUTIONS_DIR = PROJECT_DIR / "solutions"
        # Re-evaluate DB cache for new project dir
        _local_cache = PROJECT_DIR / ".fm_db_cache"
        try:
            _local_cache.mkdir(parents=True, exist_ok=True)
            _probe = _local_cache / ".probe"
            _probe.touch()
            _probe.unlink()
            DB_CACHE_DIR = _local_cache
        except Exception:
            pass  # keep existing DB_CACHE_DIR

    if not args.command:
        parser.print_help()
        sys.exit(1)

    args.func(args)


if __name__ == "__main__":
    main()
