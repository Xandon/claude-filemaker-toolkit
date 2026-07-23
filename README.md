# FileMaker Toolkit

A Cowork plugin for analyzing, reviewing, and shipping changes to FileMaker Pro database solutions via their DDR XML exports. Indexes FileMaker metadata into SQLite for fast querying, generates interactive HTML code reviews, and produces clipboard-compatible XML for paste-back into FileMaker (FM 18+, no MBS plugin required).

**Current version: 0.3.5**

## What It Does

The plugin is built around a simple loop: **index → understand → design → ship**.

- **Indexes** a FileMaker DDR XML export (typically 10–200 MB, UTF-16 LE) into a compact SQLite database in 1–3 seconds
- **Understands** your solution — queries scripts, fields, tables, layouts, relationships, value lists, custom functions, and cross-references, and diagnoses performance hotspots, anti-patterns, orphaned scripts, duplicates, and health scores
- **Reviews** scripts interactively — generates self-contained HTML reports with syntax-highlighted steps, severity-rated findings, before/after diffs, and one-click XML copy
- **Designs and ships changes** with Claude — once your solution is indexed, you can talk to Claude about adding a feature, refactoring a script, or changing schema, and Claude grounds its proposal in your actual fields, layouts, scripts, and relationships. When the plan is agreed, `/fm-implement` packages it as a paste-ready HTML deliverable: new scripts with Copy-XML buttons (FM 18+ clipboard format, no MBS plugin required), and numbered manual steps for the layout / schema work FileMaker can't paste

## Installation

Install as a Cowork plugin (Customize → Personal plugins → + → upload `.zip` or `.plugin` bundle). Once installed, the plugin exposes four slash commands (`/fm-setup`, `/fm-query`, `/fm-review`, `/fm-implement`) and a skill (`filemaker-xml-analyzer`) that triggers automatically on FileMaker-related queries.

The plugin requires Python 3.9+ with the standard library only — no external dependencies.

## Project Layout

Create one project folder per client. Each project holds one or more FileMaker solutions:

```
my-client-project/
├── CLAUDE.md                  # optional: project notes, what's been reviewed
├── .fm_db_cache/              # auto-created; holds SQLite DBs
└── solutions/
    ├── LAYER/
    │   ├── LAYER.xml          # DDR XML export
    │   ├── reviews/           # review definition JSONs, implementation specs
    │   └── output/            # generated HTML (reviews, implementation packages),
    │                          # extracted script XML
    └── ILCrop/
        ├── ILCrop.xml
        ├── reviews/
        └── output/
```

Start a Cowork session from the project folder (or point Cowork at it via the folder picker).

## Quick Start

1. **Start a Cowork session in your project folder.** If you don't have one yet, create an empty folder and put your DDR XML export inside it.

2. **Run `/fm-setup`** and provide the path to your XML file. The plugin will index the file and report the counts.

3. **Run `/fm-query <solution> health`** to get a solution health scorecard and see the biggest scripts.

4. **Run `/fm-review`** and tell Claude which script(s) you want reviewed. Claude will read the steps, look for issues, and generate a self-contained HTML report in `solutions/<name>/output/`.

5. **Discuss the change you want to make.** Just talk to Claude in plain language — *"I want to add a fungal species picker on the Mold Layers layout"*, *"refactor the Import script so it commits inside the loop"*, *"add a Notes field to Visits and surface it on the Inspection detail layout"*. Claude uses the indexed DDR to ground its proposal in your actual fields, layouts, scripts, and relationships — telling you specifically which scripts will need to be added or changed, which layouts to edit, which fields/tables/relationships to add. Iterate freely: review the plan, ask questions, add constraints, refine.

6. **Run `/fm-implement`** when you're satisfied with the plan. Claude packages everything you agreed on into a single self-contained HTML deliverable in `solutions/<name>/output/`. Open it, work through it top to bottom: for each new or updated script, click **Copy XML** and ⌘V into FileMaker Script Workspace; for layout / schema / relationship / security work, follow the numbered manual steps. The change ships in one session.

## Commands

### `/fm-setup`
Index a new DDR XML export. Creates `solutions/<name>/` with the XML and indexes it into a SQLite database under `.fm_db_cache/`.

### `/fm-query`
Run any query command against an indexed solution. Supports script analysis (`script`, `script-refs`, `script-calls`, `script-fields`, `script-cfs`, `scripts`, `deps`), schema exploration (`tables`, `table`, `field`, `field-refs`, `layouts`, `layout`, `relationships`, `value-lists`), custom functions (`custom-functions`, `custom-function`), search (`search`, `summary`), and diagnostics (`hotspots`, `trace`, `slow-patterns`, `impact`, `orphans`, `health`, `duplicates`, `no-error-handling`, `dead-code`, `anti-patterns`).

### `/fm-review`
Start an interactive code review of one or more scripts. Claude reads the steps, gathers call context, checks custom function usage, writes a review definition JSON, and generates a shareable HTML report.

### `/fm-implement`
Package the change you and Claude have just been designing into a paste-ready HTML deliverable. **This is the end of a design conversation, not the start of one** — by the time you invoke it, you've typically just spent a few minutes (or hours) talking through a feature, a refactor, or a schema update with Claude, using `/fm-query` against the indexed DDR to ground the proposal in real fields, layouts, and scripts. When you're satisfied with the plan, `/fm-implement` builds:

- **Per-script cards** with pseudocode side panel and a **Copy XML** button — paste straight into FileMaker 18+ Script Workspace (no MBS plugin required)
- **Numbered manual steps** for anything the generator can't paste — layout edits, new fields, relationship changes, security tweaks
- **Header notes** capturing the goal of the change, paste order, rollback plan, and testing checklist that came out of the conversation

The HTML is fully self-contained — share it, archive it, or just work through it once and discard. Two underlying modes that mix freely on one page:

- **Extract** existing scripts from an indexed solution (redeliver to a different file, branch, or as documentation)
- **Author** new scripts from a JSON spec Claude writes from the conversation

(The legacy `fm_manage.py paste-html` / `paste` subcommand names continue to work as aliases for `implement`, so existing scripts and muscle memory keep working.)

## Running Scripts Directly

The plugin's Python scripts live at `${CLAUDE_PLUGIN_ROOT}/scripts/`. You can bypass the slash commands and call them directly in a terminal:

```bash
python ${CLAUDE_PLUGIN_ROOT}/scripts/fm_manage.py list
python ${CLAUDE_PLUGIN_ROOT}/scripts/fm_manage.py index path/to/Solution.xml
python ${CLAUDE_PLUGIN_ROOT}/scripts/fm_manage.py query Solution script "My Script"
python ${CLAUDE_PLUGIN_ROOT}/scripts/fm_manage.py review Solution reviews/my_review.json
python ${CLAUDE_PLUGIN_ROOT}/scripts/fm_manage.py extract Solution "My Script"
python ${CLAUDE_PLUGIN_ROOT}/scripts/fm_manage.py diagnose Solution hotspots
python ${CLAUDE_PLUGIN_ROOT}/scripts/fm_manage.py implement Solution --spec spec.json -o out.html
```

## Environment Variables

| Variable | Purpose | Default |
|---|---|---|
| `FM_PROJECT_DIR` | Override the project folder | current working directory |
| `FM_DB_CACHE` | Override the SQLite cache location | `<project>/.fm_db_cache` |

## How Indexing Works

1. The parser opens the XML file in UTF-16 LE, strips invalid XML 1.0 control characters (common in FileMaker exports), and parses the full tree.
2. It walks `Structure/AddAction` and extracts: files, base tables, fields, relationships, value lists, scripts with all their steps (raw XML + human-readable translation), layouts with table occurrences and script triggers, and custom functions (signature + parameters — DDR XML does not include calculation bodies).
3. It scans every script's raw step XML for references to custom function names using regex word-boundary matching, building a `cf_references` table with one row per (script, step, custom function).
4. It writes everything to a SQLite database with indexes on the hot columns.

A 100 MB XML file indexes in 1–3 seconds and produces a ~5 MB database. All queries are sub-millisecond.

## Custom Function Framework Support

Many FileMaker solutions use a standard custom function framework (Error, DeclareVariables, StartLogTime, ExitScript, Developer, EndScriptLog). The plugin:

- Indexes all CFs and their cross-references to scripts
- Displays framework CFs as "framework" chips (styled differently when used by 50+ scripts)
- Surfaces CF usage in the HTML review so reviewers understand framework-driven error handling patterns

## HTML Output

Both review and implementation pages are self-contained (zero external dependencies, works offline, single-file share).

**Review reports** (`/fm-review`) include:

- **Overview tab**: findings sorted by severity, clickable to jump to details
- **Script tabs**: per-script view with syntax-highlighted indented steps
- **Findings panel**: severity badges, descriptions, best practice callouts, before/after diff views
- **Custom function chips**: framework references with click-to-scroll-to-usage
- **One-click XML copy**: copy the fix XML or the full corrected script for paste-back
- **Dark theme**: matches FileMaker Script Workspace aesthetic

**Implementation packages** (`/fm-implement`) include:

- **Per-script cards** with pseudocode side panel and a **Copy XML** button (FM 18+ clipboard format)
- **Manual-step sections** for layout / schema / relationship changes the agent can't paste
- **Reference resolution** against the DDR — every layout, script, table, and field name is validated before the page is built; mistakes fail loudly with "did you mean…" suggestions

## Known Limitations

- **DDR XML omits calculation bodies** for custom functions. Only signatures and parameter names are available. Use MBS plugin extraction or manual entry if you need the body.
- **Mounted filesystems** (Cowork) sometimes don't support SQLite locking. The toolkit falls back to `.fm_db_cache/` or `~/.cache/filemaker-toolkit/db_cache/` automatically.
- **Content classifier false positives**: When analyzing solutions with domain-specific terminology (laboratory sample types, analytical methods, etc.), Cowork's content classifier may flag schema terms. Workarounds: write analysis to files via Python scripts, use script IDs and step numbers rather than domain vocabulary.

## Reviewing the Plugin for Efficiency

See [PERFORMANCE.md](./PERFORMANCE.md) for a testing checklist and benchmarks.

## Changelog

See [CHANGELOG.md](./CHANGELOG.md) for the full version history.
