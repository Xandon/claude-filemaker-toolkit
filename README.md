# FileMaker Toolkit

A Cowork plugin for analyzing, reviewing, and shipping changes to FileMaker Pro database solutions via their DDR XML exports. Indexes FileMaker metadata into SQLite for fast querying, generates interactive HTML code reviews, and produces clipboard-compatible XML for paste-back into FileMaker (FM 18+, no MBS plugin required).

**Current version: 0.3.5**

Real-world validation: **10 DDRs / 1.29 GB of XML indexed in ~45 seconds**, peak RSS under 500 MB even on the largest single file (SAMPLES: 248 MB XML, 526 layouts, 4,013 fields → 373 MB peak). See [PERFORMANCE.md](./PERFORMANCE.md) for the full benchmark table.

## What It Does

The plugin is built around a simple loop: **index → understand → design → ship**.

- **Indexes** a FileMaker DDR XML export in seconds using a streaming parser. Peak memory is bounded by the largest single script or layout — not the whole document — so a 360 MB DDR indexes in a few hundred MB of RAM, not multiple GB
- **Understands** your solution — queries scripts, fields, tables, layouts, relationships, value lists, custom functions, and cross-references, and diagnoses performance hotspots, anti-patterns, orphaned scripts, duplicates, and health scores
- **Reviews** scripts interactively — generates self-contained HTML reports with syntax-highlighted steps, severity-rated findings, before/after diffs, and one-click XML copy
- **Designs and ships changes** with Claude — once your solution is indexed, you can talk to Claude about adding a feature, refactoring a script, or changing schema, and Claude grounds its proposal in your actual fields, layouts, scripts, and relationships. When the plan is agreed, `/fm-implement` packages it as a paste-ready HTML deliverable: new scripts with Copy-XML buttons (FM 18+ clipboard format, no MBS plugin required), and numbered manual steps for the layout / schema work FileMaker can't paste

## Installation

Install as a Cowork plugin (Customize → Personal plugins → + → upload `.zip` or `.plugin` bundle). Once installed, the plugin exposes four slash commands (`/fm-setup`, `/fm-query`, `/fm-review`, `/fm-implement`) and a skill (`filemaker-xml-analyzer`) that triggers automatically on FileMaker-related queries.

The plugin requires Python 3.9+ with the standard library only — no external dependencies. Everything the plugin does at runtime uses stock stdlib modules (`xml.etree.ElementTree`, `sqlite3`, `codecs`, `tempfile`, `re`), so the same scripts work anywhere `python3` runs — including on the user's own machine via the bundled wrapper (see [Large DDRs](#large-ddrs-native-terminal-run-required) below).

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

## Large DDRs: native Terminal run required

For any DDR export **larger than 50 MB**, or any DDR that lives on your own machine while you're in a cloud Cowork sandbox, `/fm-setup` will refuse to index in-sandbox and route you to a native Terminal run on your own machine instead. The file never leaves your device. This is a hard rule — there's no cloud-transfer escape hatch, by design.

The plugin ships a one-file wrapper that makes the native run trivial: **`scripts/fm_index_wrapper.sh`**. Drop just this one file (no Python needed) into the folder that holds your DDR XMLs, then:

```bash
cd "<folder containing the XML>"
chmod +x fm_index_wrapper.sh                  # once, if the exec bit is stripped
./fm_index_wrapper.sh "MySolution.xml"        # index + summary in one command
# or, for a batch:
for f in *.xml; do ./fm_index_wrapper.sh "$f"; done
```

The wrapper auto-detects `fm_manage.py` inside your installed Cowork plugin, invokes it against the current directory (so `solutions/` and `.fm_db_cache/` land here), and prints the index counts + `Peak RSS: N MB` for each file. Environment overrides:

| Variable | Purpose |
|---|---|
| `FM_MANAGE_PATH` | Absolute path to `fm_manage.py` (bypasses auto-detect) |
| `FM_PYTHON` | Python interpreter (default: `python3`) |
| `FM_PROJECT_DIR` | Where `solutions/` and `.fm_db_cache/` land (default: `$PWD`) |

Real-world calibration on a 2020 MacBook Pro: the plugin indexed a 10-DDR batch (BATCH, Core_Contacts, LAYER, MENU, MetalsQC, NVL Inspection Data, NVL Inspection, NVLwd, SAMPLES, Staff — totalling 1.29 GB of XML) in **~45 seconds** with peak RSS staying under **500 MB on every single file**. See [PERFORMANCE.md](./PERFORMANCE.md) for the file-by-file breakdown.

## Environment Variables

| Variable | Purpose | Default |
|---|---|---|
| `FM_PROJECT_DIR` | Override the project folder | current working directory |
| `FM_DB_CACHE` | Override the SQLite cache location | `<project>/.fm_db_cache` |
| `FM_MANAGE_PATH` | (Wrapper only) absolute path to `fm_manage.py`, bypasses auto-detect | — |
| `FM_PYTHON` | (Wrapper only) Python interpreter | `python3` |

## How Indexing Works

The indexer streams the DDR XML end-to-end — it never holds the whole document in memory.

1. **Stream-transcode to UTF-8.** The source is read in 1 MiB chunks through `codecs.getincrementaldecoder` (the sniffed encoding — usually UTF-16 LE with BOM), invalid XML 1.0 control characters are stripped via a precomputed `str.translate` table (much faster than regex over hundreds of MB), and the XML declaration is rewritten to advertise UTF-8. The result lands in a `tempfile.NamedTemporaryFile` that gets unlinked in a `finally` block.
2. **`xml.etree.ElementTree.iterparse` walks the temp file** with `start` / `end` events. Each catalog element (`FieldsForTables`, `ValueListCatalog`, `RelationshipCatalog`, `ScriptCatalog`, `LayoutCatalog`, `ExternalDataSourceCatalog`, `CustomFunctionCatalog` in both spellings) dispatches to a per-catalog handler on its `end` event and is then cleared.
3. **Memory-heavy catalogs stream one child at a time.** Every `Script` end event inside `StepsForScripts`, every `Layout` end event inside `LayoutCatalog`, and every `FieldCatalog` end event inside `FieldsForTables` is processed and cleared individually. That means peak memory tracks the largest single script / layout / table's fields — not the whole catalog. A DDR with 526 layouts hits the same peak as one with 5.
4. **State flags** (`in_add_action`, `in_steps_for_scripts`, `in_layout_catalog`, `in_fields_for_tables`) keep extraction scoped to the top-level `<AddAction>` container, matching the DOM parser's behaviour on diff-shaped DDRs that also carry `<ModifyAction>` / `<DeleteAction>`.
5. **Cross-references built at the end.** After all script steps are inserted, the indexer scans `script_steps.raw_xml` in SQL for custom-function name matches (using a compiled regex sorted longest-first) and inserts the `cf_references` rows — all in-database, no XML in memory.
6. **Everything lands in SQLite** with indexes on the hot columns and a peak-RSS number printed at the end of the run (POSIX only; normalized: macOS reports bytes, Linux KiB).

**Observed on real DDRs (2020 MacBook Pro, `Python 3.9.13`):**

| Size | Scripts | Steps | Layouts | Fields | Elapsed | Peak RSS |
|---|---|---|---|---|---|---|
| 16 MB | 238 | 5,741 | 55 | 364 | 0.9 s | 75 MB |
| 118 MB | 797 | 34,355 | 159 | 801 | 6.0 s | 323 MB |
| 143 MB | 332 | 20,488 | 191 | 755 | 7.1 s | 320 MB |
| 236 MB | 594 | 17,328 | 337 | 1,000 | 4.0 s | 212 MB |
| 248 MB | 694 | 27,988 | 526 | 4,013 | 7.8 s | 373 MB |
| 360 MB | 761 | 20,690 | 416 | 2,195 | 6.6 s | 284 MB |

A legacy DOM path (`parse_xml_dom` / `index_file(..., use_dom=True)`) is retained for correctness comparison but is never the default.

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
- **Large DDRs cannot be indexed in a cloud sandbox** (see [above](#large-ddrs-native-terminal-run-required)). This is a hard policy, not a technical limitation — the streaming indexer could handle them, but a device-resident DDR must not move. Use the bundled `fm_index_wrapper.sh` on your own machine instead.
- **Content classifier false positives**: When analyzing solutions with domain-specific terminology (laboratory sample types, analytical methods, etc.), Cowork's content classifier may flag schema terms. Workarounds: write analysis to files via Python scripts, use script IDs and step numbers rather than domain vocabulary.

## Reviewing the Plugin for Efficiency

See [PERFORMANCE.md](./PERFORMANCE.md) for a testing checklist and benchmarks.

## Changelog

See [CHANGELOG.md](./CHANGELOG.md) for the full version history.
