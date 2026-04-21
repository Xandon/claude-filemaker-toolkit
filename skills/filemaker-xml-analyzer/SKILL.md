---
name: filemaker-xml-analyzer
description: >
  Analyze, review, and modify FileMaker Pro database solutions via their DDR XML exports.
  Use this skill whenever the user mentions FileMaker, .fmp12, DDR XML, FM scripts,
  FileMaker layouts, FileMaker schema, FileMaker relationships, or wants to review/debug
  FileMaker script logic. Also trigger when the user uploads or references large XML files
  that contain FMSaveAsXML elements, ScriptCatalog, FieldsForTables, LayoutCatalog, or
  StepsForScripts sections. This skill handles: script code review, cross-reference analysis,
  schema exploration, script translation to human-readable format, dependency mapping, custom
  function indexing, and generating modified script XML for paste-back via MBS plugin. Even if
  the user just says "look at my XML" or "help with this script" and the file turns out to be
  a FileMaker DDR, use this skill.
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

# Extract a script as MBS-compatible clipboard XML
python ${CLAUDE_PLUGIN_ROOT}/scripts/fm_manage.py extract <solution> <script_name_or_id>

# Diagnostic commands (hotspots, impact, slow-patterns, health, complexity, etc.)
python ${CLAUDE_PLUGIN_ROOT}/scripts/fm_manage.py diagnose <solution> <command>

# Generate interactive relationship graph
python ${CLAUDE_PLUGIN_ROOT}/scripts/fm_manage.py graph <solution> [--focus "TO Name"] [--depth 2]

# Compare two versions of a solution (diff)
python ${CLAUDE_PLUGIN_ROOT}/scripts/fm_manage.py diff <solution> <old.db> diff-summary
python ${CLAUDE_PLUGIN_ROOT}/scripts/fm_manage.py diff <solution> <old.db> diff-script "Script Name"
python ${CLAUDE_PLUGIN_ROOT}/scripts/fm_manage.py diff <solution> <old.db> diff-html --output changes.html

# Auto-generate bulk code review from diagnostics
python ${CLAUDE_PLUGIN_ROOT}/scripts/fm_manage.py bulk-review <solution> --min-steps 20 --checks no-error-handling,slow-patterns
```

The plugin exposes three slash commands that wrap these: `/fm-setup`, `/fm-query`, and `/fm-review`.

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
| `tos [pattern]` | List table occurrences with base table mapping (FM 22+) |
| `to <name>` | Show TO details, relationships, and scripts referencing its fields (FM 22+) |

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
| `complexity <name\|id>` | Deep complexity analysis of a single script (cyclomatic, nesting, risk) |
| `complexity-report [n]` | Ranked complexity report for all scripts with A–F grades |
| `complexity-html --output file` | Generate interactive HTML complexity dashboard |

### Diff (Version Comparison)
| Command | Description |
|---------|-------------|
| `diff <solution> <old.db> diff-summary` | High-level change summary between two DB versions |
| `diff <solution> <old.db> diff-scripts` | Detailed script changes using step hash comparison |
| `diff <solution> <old.db> diff-script <name>` | Side-by-side diff of a specific script |
| `diff <solution> <old.db> diff-fields` | Field-level changes by table |
| `diff <solution> <old.db> diff-html` | Self-contained HTML diff report |

### Relationship Graph
| Command | Description |
|---------|-------------|
| `graph <solution>` | Generate interactive HTML relationship graph |
| `graph <solution> --focus "TO"` | Center on a specific table occurrence |
| `graph <solution> --focus "TO" --depth 2` | Show only TOs within N hops |

### Bulk Code Review
| Command | Description |
|---------|-------------|
| `bulk-review <solution>` | Auto-generate review from diagnostic checks |
| `bulk-review <solution> --filter "Admin/*"` | Filter scripts by folder path pattern |
| `bulk-review <solution> --min-steps 20` | Only review scripts with 20+ steps |
| `bulk-review <solution> --checks no-error-handling,slow-patterns,dead-code` | Choose which checks to run |

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
           "after_human": "Fixed code"
         }
       }
     }]
   }
   ```

2. Generate the HTML:
   ```bash
   python ${CLAUDE_PLUGIN_ROOT}/scripts/fm_manage.py review <solution> <review.json>
   ```

The output HTML is self-contained (no external dependencies). It has an Overview tab, per-script tabs with syntax-highlighted steps, a findings panel with before/after diffs, custom function chips for framework references, and one-click XML copy for MBS paste-back. **FM 22+**: CF chips now show the full calculation body on click — expandable code panel with a "Copy Body" button.

## Generating Modified Script XML

For MBS plugin paste-back:

1. `python ${CLAUDE_PLUGIN_ROOT}/scripts/fm_manage.py extract <solution> <script>` — extract the original
2. Discuss changes with the user
3. Edit the XML or build new steps with `fm_xml_gen.py generate_step_xml()` (supports 49+ step types including Set Field, Perform Script, Show Custom Dialog, Go to Related Record, Install OnTimer, New Window, Open URL, Import/Export Records, Replace Field Contents, Perform Script on Server, Truncate Table, and more)
4. Wrap in FMObjectList format if building from scratch

## FileMaker XML Structure Reference

### FM 21 and earlier (FMSaveAsXML v2.2.2.0)

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

### FM 22+ (FMSaveAsXML v2.2.3.0)

FM 22 introduces a two-part AddAction/ModifyAction architecture and several new sections:

```
FMSaveAsXML
└── Structure
    ├── AddAction
    │   ├── FieldsForTables (table + field definitions — base records)
    │   ├── ScriptCatalog (script metadata)
    │   ├── LayoutCatalog (layout objects — base records)
    │   ├── CalcsForCustomFunctions (NEW — CF calculation bodies in CDATA)
    │   ├── TableOccurrenceCatalog (NEW — full TO graph with base table refs)
    │   ├── StepsForScripts (script step logic — now includes hash attributes)
    │   └── CustomFunctionsCatalog
    └── ModifyAction (NEW — field calc formulas, layout modifications)
        ├── FieldsForTables (field calculation formulas not in AddAction)
        └── LayoutCatalog (layout modifications)
```

Key FM 22 changes the parser handles:
- **CalcsForCustomFunctions**: CF calculation bodies are now included in the DDR export (previously unavailable). The parser extracts these and stores them as `calculation_text` on the `custom_functions` table.
- **ModifyAction**: Contains field calculation formulas (auto-enter calcs, validations) and layout modifications that are separate from the base definitions in AddAction. The parser merges these back into the `fields` table.
- **TableOccurrenceCatalog**: Full table occurrence graph with base table references, UUIDs, and view settings. Indexed into the `table_occurrences` table.
- **Step hash attributes**: Each script step now carries a `hash` attribute for change detection. Stored in `script_steps.step_hash`.
- **Idempotent re-indexing**: Running the indexer again on the same file safely replaces the old data rather than duplicating it.

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
- **FM 22+**: Custom function calculation bodies are now included in the DDR export and automatically parsed. Use `custom-function <name>` to see the full CF body. For FM 21 and earlier, CF bodies are not available in the DDR — only signatures and parameter names.
- Re-indexing is idempotent: running the indexer on a previously indexed file replaces old data cleanly
