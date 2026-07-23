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
PROJECT_DIR = Path(os.environ.get("FM_PROJECT_DIR", Path.cwd())).resolve()
SOLUTIONS_DIR = PROJECT_DIR / "solutions"
TOOLKIT_DIR = SCRIPT_DIR

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
    # Strip fm_parser's own "Database saved to: <cache path>" tail line: we
    # copy the DB to the solutions folder below and unlink the cache copy,
    # so that message would be stale by the time it hit the user's screen.
    # We print our own "Database saved to: <final path>" after the copy.
    filtered_stdout = '\n'.join(
        line for line in result.stdout.splitlines()
        if not line.startswith('Database saved to:')
    )
    print(filtered_stdout)
    if result.returncode != 0:
        print(result.stderr)
        sys.exit(1)

    # Try to copy to the solution directory; if that fails, keep in cache
    target_db = sol_dir / db_name
    db_location = temp_db  # default to cache
    try:
        shutil.copy2(str(temp_db), str(target_db))
        # Verify the copy is readable by SQLite
        conn = sqlite3.connect(str(target_db))
        conn.execute("SELECT COUNT(*) FROM scripts")
        conn.close()
        # Success — the solution dir copy works
        db_location = target_db
        temp_db.unlink()
    except Exception:
        # Keep DB in cache — it's still fully functional there
        db_location = temp_db
        print(f"  (DB stored in cache: {temp_db} — mount FS doesn't support SQLite)")

    print(f"Database saved to: {db_location}")

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

    cmd = [sys.executable, str(FM_REVIEW_GEN), str(sol_data["db"]),
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


def cmd_paste_html(args):
    """Build a paste-ready implementation package (extract + author).

    Subcommand: ``implement`` (aliases: ``paste-html``, ``paste``). Produces
    a self-contained HTML page bundling Copy-XML buttons for scripts and
    (when extended) ordered manual steps for layout / schema changes.
    """
    sol_name, sol_data = resolve_solution(args.solution)
    if sol_data.get("db") is None:
        print(f"Solution '{sol_name}' is not indexed yet.")
        sys.exit(1)

    items = []
    for s in args.script or []:
        items.append(("extract", s))
    for s in args.spec or []:
        items.append(("spec", s))
    if not items:
        print("Provide at least one --script or --spec.")
        sys.exit(2)

    out = args.output
    if not out:
        out_dir = sol_data["dir"] / "output"
        out_dir.mkdir(parents=True, exist_ok=True)
        out = str(out_dir / "implementation.html")

    # Import the generator (alongside this script in scripts/)
    sys.path.insert(0, str(SCRIPT_DIR))
    try:
        from fm_paste_html_gen import generate_paste_html, ResolveError, SpecError
    except ImportError as e:
        print(f"Could not import fm_paste_html_gen: {e}")
        sys.exit(1)

    notice_html = None
    if getattr(args, "notice_html_file", None):
        nh_path = Path(args.notice_html_file)
        if not nh_path.exists():
            print(f"ERROR: --notice-html-file not found: {nh_path}")
            sys.exit(2)
        notice_html = nh_path.read_text(encoding="utf-8")

    try:
        result_path = generate_paste_html(
            db_path=str(sol_data["db"]),
            items=items,
            output_path=out,
            title=args.title,
            include_human=not args.no_human,
            extra_pills=[f"Solution: {sol_name}"],
            notice_html=notice_html,
        )
    except (ResolveError, SpecError) as e:
        print(f"ERROR: {e}")
        sys.exit(2)

    n_extract = sum(1 for k, _ in items if k == "extract")
    n_spec = sum(1 for k, _ in items if k == "spec")
    print(f"Wrote: {result_path}")
    print(f"  Extracted scripts: {n_extract}")
    print(f"  Spec files:        {n_spec}")


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


def main():
    parser = argparse.ArgumentParser(
        description="FileMaker Solution Manager — manage multiple DDR XML solutions",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
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
  python fm_manage.py implement LAYER --script "Close Card Window" -o out.html
  python fm_manage.py implement LAYER --spec picker_spec.json -o picker.html
  python fm_manage.py implement LAYER --script 974 --spec patches.json
  # (paste-html and paste are kept as aliases for backward compatibility)
        """
    )
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
    sub_diag.add_argument("diag_command", help="Diagnostic command: health, hotspots, trace, slow-patterns, impact, orphans, duplicates, no-error-handling, dead-code, anti-patterns")
    sub_diag.add_argument("extra", nargs="*", help="Additional arguments")
    sub_diag.set_defaults(func=cmd_diagnose)

    # implement (formerly "paste-html") — build a paste-ready implementation
    # package (scripts, layouts, schema instructions). The legacy names
    # "paste-html" and "paste" are kept as aliases for backward compatibility
    # so existing scripts and muscle memory keep working.
    sub_paste = subparsers.add_parser(
        "implement", aliases=["paste-html", "paste"],
        help="Build a paste-ready implementation package "
             "(scripts, layouts, schema)")
    sub_paste.add_argument("solution", help="Solution name (partial match OK)")
    sub_paste.add_argument("--script", action="append", default=[],
                           help="Existing script name or id to extract (repeatable)")
    sub_paste.add_argument("--spec", action="append", default=[],
                           help="Spec JSON describing new scripts (repeatable)")
    sub_paste.add_argument("--title", help="Page title")
    sub_paste.add_argument("--no-human", action="store_true",
                           help="Suppress the pseudocode panel (XML only)")
    sub_paste.add_argument("--notice-html-file",
                            help="Inject raw HTML as the notice block (no escaping). "
                                 "Overrides spec.meta.notes and structured meta fields. "
                                 "Use when you want full control over the notice HTML.")
    sub_paste.add_argument("-o", "--output",
                           help="Output HTML path "
                                "(default: solutions/<solution>/output/implementation.html)")
    sub_paste.set_defaults(func=cmd_paste_html)

    # summary
    sub_summary = subparsers.add_parser("summary", aliases=["info"],
                                         help="Show detailed summary of a solution")
    sub_summary.add_argument("solution", help="Solution name")
    sub_summary.set_defaults(func=cmd_summary)

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(1)

    args.func(args)


if __name__ == "__main__":
    main()
