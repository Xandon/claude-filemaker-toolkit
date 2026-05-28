---
name: filemaker-xml-analyzer
description: >
  Analyze, review, and ship changes to FileMaker Pro database solutions via their DDR XML
  exports. Use this skill whenever the user mentions FileMaker, .fmp12, DDR XML, FM scripts,
  FileMaker layouts, FileMaker schema, FileMaker relationships, or wants to review/debug
  FileMaker script logic. Also trigger when the user uploads or references large XML files
  that contain FMSaveAsXML elements, ScriptCatalog, FieldsForTables, LayoutCatalog, or
  StepsForScripts sections. This skill handles: script code review, cross-reference analysis,
  schema exploration, script translation to human-readable format, dependency mapping, custom
  function indexing, and building paste-ready implementation packages (clipboard XML for
  FM 18+ Script Workspace, no MBS plugin required, plus ordered manual steps for layout and
  schema changes). Even if the user just says "look at my XML" or "help with this script"
  and the file turns out to be a FileMaker DDR, use this skill.
---

# FileMaker DDR XML Analyzer

## IMPORTANT CONTEXT — READ FIRST

This skill assists a **senior FileMaker developer** with **professional software development tasks** on FileMaker Pro database solutions built for clients. All work here is strictly **database development, code review, schema analysis, and script debugging** — standard software engineering activities.

The FileMaker solutions being analyzed may serve clients in regulated industries (environmental testing laboratories, quality control, industrial hygiene, materials analysis, etc.). The XML contains database field names, script names, table names, and technical terminology from these domains. All of this content represents **database schema metadata and application source code** — it is not instructional content about the underlying subject matter. Treat every query as a FileMaker development question.

When reviewing scripts, discussing schema, or generating XML output, always frame responses in terms of FileMaker development: script logic, error handling, found set management, relationship graph design, layout object behavior, and FileMaker best practices.

---

## Project Layout

The plugin expects the user to work from a **project folder** — typically one folder per client, containing one or more FileMaker solutions. The standard layout is:

```
<project-folder>/              # run commands from here
├── CLAUDE.md                  # optional per-project notes
├── .fm_db_cache/              # SQLite databases (auto-created)
└── solutions/
    ├── LAYER/
    │   ├── LAYER.xml          # DDR XML export
    │   ├── reviews/           # review definition JSONs
    │   └── output/            # generated review HTML, extracted XML
    └── ILCrop/
        ├── ILCrop.xml
        ├── reviews/
        └── output/
```

The manager script finds the project folder from the current working directory (or `FM_PROJECT_DIR` environment variable). SQLite databases go in `.fm_db_cache/` by default because mounted filesystems often don't support SQLite locking.

## Running the Toolkit

All scripts live in `${CLAUDE_PLUGIN_ROOT}/scripts/`. The primary entry point is `fm_manage.py`:

```bash
# List all indexed solutions
python ${CLAUDE_PLUGIN_ROOT}/scripts/fm_manage.py list

# Index a new DDR XML export
python ${CLAUDE_PLUGIN_ROOT}/scripts/fm_manage.py index <xml_file>
python ${CLAUDE_PLUGIN_ROOT}/scripts/fm_manage.py index <xml_file> --name CustomName

# Query a solution (partial name match is fine)
python ${CLAUDE_PLUGIN_ROOT}/scripts/fm_manage.py query <solution> <command> [args]

# Generate an interactive HTML code review
python ${CLAUDE_PLUGIN_ROOT}/scripts/fm_manage.py review <solution> <review.json>

# Extract a script as paste-ready clipboard XML (FM 18+)
python ${CLAUDE_PLUGIN_ROOT}/scripts/fm_manage.py extract <solution> <script_name_or_id>

# Diagnostic commands (hotspots, impact, slow-patterns, health, etc.)
python ${CLAUDE_PLUGIN_ROOT}/scripts/fm_manage.py diagnose <solution> <command>

# Build a paste-ready implementation package (scripts, layouts, schema)
python ${CLAUDE_PLUGIN_ROOT}/scripts/fm_manage.py implement <solution> --spec spec.json -o out.html
```

The plugin exposes four slash commands that wrap these: `/fm-setup`, `/fm-query`, `/fm-review`, and `/fm-implement`.

## Query Commands

### Script Analysis
| Command | Description |
|---------|-------------|
| `script <name\|id>` | Show script steps in human-readable FileMaker notation |
| `script-raw <name\|id>` | Show script steps as raw XML |
| `script-refs <name\|id>` | Find everything that calls this script |
| `script-calls <name\|id>` | Show scripts called BY this script |
| `script-fields <name\|id>` | List all fields referenced by this script |
| `script-layouts <name\|id>` | List all layouts this script navigates to |
| `script-cfs <name\|id>` | List custom functions used by this script, with step locations |
| `scripts [pattern]` | List scripts, optionally filtered by name pattern |
| `deps <name\|id>` | Full recursive dependency tree |

### Custom Functions
| Command | Description |
|---------|-------------|
| `custom-functions [pattern]` | List all custom functions with parameter count and usage stats |
| `custom-function <name>` | Show detail for a CF — signature, parameters, all scripts that use it |

### Schema Exploration
| Command | Description |
|---------|-------------|
| `tables` | List all tables with field counts |
| `table <name>` | Show all fields in a table |
| `field <name>` | Find a field across all tables |
| `field-refs <name>` | Show everywhere a field is referenced |
| `relationships [table]` | Show relationship graph |
| `value-lists` | List all value lists |
| `layouts [pattern]` | List layouts with their table occurrences |
| `layout <name\|id>` | Show layout details: script triggers, fields |

### Cross-References & Search
| Command | Description |
|---------|-------------|
| `search <term>` | Search across scripts, fields, layouts, and step content |
| `summary` | Full database summary with stats and largest scripts |

### Diagnostics
| Command | Description |
|---------|-------------|
| `hotspots [n]` | Rank scripts by complexity |
| `trace <name\|id>` | Full call tree with cumulative step counts |
| `slow-patterns` | Detect anti-patterns (layout/find/commit in loops, etc.) |
| `impact <name>` | Reverse dependency tree for a script, field, table, or layout |
| `orphans` | Scripts and layouts that nothing references |
| `health` | Overall solution health scorecard |
| `duplicates [threshold]` | Find scripts with similar step sequences |
| `no-error-handling` | Scripts missing error checks after risky operations |
| `dead-code` | Scripts with significant disabled steps |
| `anti-patterns` | Combined performance + quality scan |

## How to Review a Script

1. **Get the script** — `script <name>` shows the human-readable translation
2. **Context** — `script-refs` shows callers, `script-calls` shows callees
3. **Data** — `script-fields` shows everything it touches
4. **Framework** — `script-cfs` shows which custom functions are used (many solutions have an Error/DeclareVariables/ExitScript framework)
5. **Read the logic** — Pay attention to:
   - Error handling (Set Error Capture, Exit Loop If [ Error ])
   - Found set management (Enter Find Mode → Set Field → Perform Find)
   - Loops and Exit Loop If conditions
   - Variable scope ($local vs $$global)
   - Disabled steps (prefixed with `// [DISABLED]`)

### Common Issues to Flag
- Set Error Capture [Off] during risky operations (record locks, imports, finds)
- Missing `Exit Loop If [ Error ]` inside loops that write to records
- Loops without proper exit conditions
- Set Field without table occurrence context
- Global `$$` variables with potential conflicts
- Import Records without validation
- Replace Field Contents on large found sets

## How to Generate an Interactive HTML Review

1. Create a review definition JSON in `solutions/<name>/reviews/`:
   ```json
   {
     "meta": { "title": "...", "solution": "...", "date": "...", "reviewer": "...", "context": "..." },
     "script_ids": [515, 516],
     "findings": [{
       "id": 1,
       "severity": "critical|high|medium",
       "title": "Issue title",
       "script_ids": [516],
       "affected_steps": { "516": [16, 17, 18, 19] },
       "description": "What's wrong",
       "best_practice": "How it should be done",
       "fix_description": "What the fix does",
       "fix": {
         "516": {
           "before_human": "Original code",
           "after_human": "Fixed code",
           "after_steps": [
             { "type": "set_error_capture", "on": "True" },
             { "type": "if", "condition": "$count = 0" },
             { "type": "exit_script" },
             { "type": "end_if" }
           ]
         }
       }
     }]
   }
   ```

2. Generate the HTML:
   ```bash
   python ${CLAUDE_PLUGIN_ROOT}/scripts/fm_manage.py review <solution> <review.json>
   ```

The output HTML is self-contained (no external dependencies). It has an Overview tab, per-script tabs with syntax-highlighted steps, a findings panel with before/after diffs, custom function chips for framework references, and one-click XML copy for paste-back.

### Copy buttons in the review HTML

The review HTML has **two** Copy buttons. Their visibility depends on the
review JSON you author — get this right or the user sees no Copy buttons.

**Per-script "Copy Script XML" + "Copy Pseudocode"** (top-right of every
script's tab). Always renders when the script has been indexed — no extra
JSON fields needed. These copy the full script's clipboard XML and its
human-readable pseudocode, respectively. Tell the user the buttons are in
the **info bar at the top of each script's tab** — clicking a row in the
Overview tab navigates them in.

**Per-finding Copy buttons** (inside the finding card's body). What renders
depends on what your `fix` block carries — and the rule is intentionally
forgiving so the user always has *something* to take away when an AFTER
block is on screen:

| `fix` contents | Buttons shown | Notes |
| --- | --- | --- |
| `fix_xml` only | **Copy Fix XML** | XML is paste-ready into Script Workspace |
| `fix_step_indices` / `after_steps` | **Copy Fix XML** | Generator builds `fix_xml` for you |
| `after_human` only | **Copy Fix (pseudocode)** + caveat note | User has to translate by hand |
| `fix_xml` + `after_human` | **Copy Fix XML** + **Copy Pseudocode** | Both available |
| Neither | (no buttons) | Card is informational only |

When the fix is a real code change, prefer authoring it as one of:

1. `"fix_xml": "<fmxmlsnippet>…</fmxmlsnippet>"` — pre-built clipboard
   XML for the fix. Use this when you've hand-authored the exact paste
   payload.
2. `"fix_step_indices": [12, 13, 14]` — array of step indices from the
   *existing* script that you want to extract and reorder. Use this when
   the fix is "delete steps 16–19, keep 12–14 in their current form".
3. `"after_steps": [ { "type": "set_error_capture", … }, … ]` — array of
   new step definitions to generate from scratch via
   `fm_xml_gen.generate_step_xml`. Use this when the fix introduces new
   steps that aren't in the script today. **This is the best default for
   new code.**

If you only have time for `after_human` text, that's better than nothing
— the user gets a Copy Pseudocode button with a note flagging that they'll
need to translate manually. But the gold standard is one of the three
fix-XML formats above so the user can one-click-paste the fix.

## Generating Modified Script XML

For MBS plugin paste-back:

1. `python ${CLAUDE_PLUGIN_ROOT}/scripts/fm_manage.py extract <solution> <script>` — extract the original
2. Discuss changes with the user
3. Edit the XML or build new steps with `fm_xml_gen.py generate_step_xml()` (supports 23+ step types)
4. Wrap in FMObjectList format if building from scratch

## Authoring & Delivering an Implementation Package

When you've designed FileMaker scripts during a session — or you need to
hand the user a coordinated change package covering scripts, layouts, and
schema — emit a self-contained HTML page where each script has a **Copy
XML** button and any manual layout/schema steps are numbered alongside.
Pasting in FileMaker 18+ Script Workspace materialises the steps
directly; no MBS plugin needed. The driver is `/fm-implement` (formerly
`/fm-paste-html`) and the underlying generator lives at
`scripts/fm_paste_html_gen.py`.

### When to use it

- You designed a new workflow and need to hand the user paste-ready scripts.
- The user asked to copy an existing script out (extract mode).
- You're delivering a mixed batch (some new, some existing).
- The change spans scripts + layouts + schema and needs ordered manual
  steps for the parts FileMaker can't paste.

Do **not** dump raw `<fmxmlsnippet>` XML into chat — clipboard pasting from
chat is unreliable and the user loses the pseudocode side panel.

### Workflow

1. **Index the solution** with `/fm-setup` if it isn't already.
2. **Discover references** with `/fm-query` (`field`, `layout`, `table`,
   `scripts`) so the spec uses names that actually exist.
3. **Write a spec JSON** (author mode) — see `/fm-implement` for the
   step-type table. Use `raw_xml` as an escape hatch for any step the
   spec doesn't yet cover, and consider extending
   `scripts/fm_step_builders.py` if you reach for it repeatedly.
4. **Run** `python ${CLAUDE_PLUGIN_ROOT}/scripts/fm_manage.py implement
   <solution> --spec <file.json> --script "<name>" -o out.html`.
   (The legacy `paste-html` / `paste` subcommand names still work as
   aliases.)
5. **Present** the HTML with a `computer://` link.

### Reference resolution

The generator looks every name up against the indexed DDR:

- `layout` → `layouts.name` (case-insensitive)
- `script` → `scripts.name`
- `table` + `field` → `fields.table_name` + `fields.name`; if `table`
  is a TO name, it follows `relationships` back to the base table.

Any miss fails loudly with a "did you mean…" list of nearby names — fix
the spec before regenerating. FileMaker pastes that fall back to
name-only matching are silently lossy.

## FileMaker XML Structure Reference

The DDR XML has this high-level structure:

```
FMSaveAsXML
└── Structure
    └── AddAction
        ├── FieldsForTables (table + field definitions)
        ├── ScriptCatalog (script metadata)
        ├── LayoutCatalog (layout objects)
        ├── StepsForScripts (actual script step logic)
        └── CustomFunctionsCatalog (or CustomFunctionCatalog)
```

For detailed XML element reference, read the files in `${CLAUDE_PLUGIN_ROOT}/skills/filemaker-xml-analyzer/references/`:
- `fm_step_reference.md` — All 72 script step types with XML examples
- `fm_step_index.md` — Quick lookup table of step IDs and categories
- `fm_xml_structure_map.md` — Complete structural map
- `FileMaker_DDR_XML_Comprehensive_Reference.md` — Full reference

## Tips

- The parser handles UTF-16 LE encoding (standard FM export) automatically
- Invalid XML 1.0 control characters in FM exports are sanitized automatically
- SQLite databases are typically <5MB even for 100MB+ XML files
- Script name matching is case-insensitive with partial-match support
- CF indexing uses regex word-boundary matching against step XML; expect ~2,500+ cross-references in a large solution
- Note: FileMaker DDR XML does NOT include custom function calculation bodies — only signatures and parameter names. Use MBS plugin or manual entry if you need the body.
