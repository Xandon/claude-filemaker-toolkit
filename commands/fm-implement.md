---
description: Build a paste-ready implementation package for FileMaker scripts, layouts, and schema changes
---

The user wants a self-contained HTML page that bundles **everything needed
to implement a change** in their FileMaker solution — a new feature, an
update to an existing script, a layout adjustment, or a schema tweak. Each
script on the page has a **Copy XML** button that puts clipboard-format
FileMaker XML (FM 18+) on the clipboard, ready to paste directly into
Script Workspace — no MBS plugin needed.

For non-script work (layout / schema changes) the page also acts as an
**ordered implementation guide** with step-by-step manual instructions
alongside the paste-ready script blocks.

## What an implementation package can contain

| Section | What it is | Use when |
| --- | --- | --- |
| **Extract** | Existing scripts from an indexed solution | Re-pasting known scripts (different file, branch, or documentation) |
| **Author** | New scripts generated from a JSON spec | Claude has just designed scripts and needs to ship them as paste-ready XML |
| **Manual steps** | Numbered instructions (layout edits, field adds, relationship changes, security tweaks) | The change touches layouts/schema — anything the agent cannot apply via XML paste |
| **Notes** | Free-form context (rollback plan, paste order, testing checklist) | Documenting *how* to apply the change safely |

One HTML page can mix all four freely. Order matters when scripts call
each other — list them in the order the user should paste.

## Workflow

1. **Confirm the solution is indexed.** The HTML generator reads the SQLite
   `.db` produced by `/fm-setup`. If the user hasn't indexed it, run
   `/fm-setup` first.

2. **Decide what's on the page.** Ask the user what they want to ship:
   - Which existing scripts to extract (if any)
   - Which new scripts to author
   - Any layout / schema / relationship / security changes that require
     manual steps in FileMaker

   For author mode you may need to discover field / layout / TO names —
   run `/fm-query <solution> field <pattern>`,
   `/fm-query <solution> layout <pattern>`,
   `/fm-query <solution> table <name>` first.

3. **Write the spec JSON** (author mode only). Save it to
   `solutions/<solution>/reviews/<name>.json` or
   `solutions/<solution>/output/<name>.spec.json` — see "Spec JSON shape"
   below, and `examples/picker_spec_example.json` for a full reference.

4. **Run the generator:**

   ```bash
   python ${CLAUDE_PLUGIN_ROOT}/scripts/fm_manage.py implement <solution> \
       [--script "<name|id>"  ...]   \
       [--spec  <file.json>   ...]   \
       [--title "<page title>"]      \
       [--no-human]                  \
       [-o <output.html>]
   ```

   Default output is `solutions/<solution>/output/implementation.html`.

   > **Backward compatibility:** `paste-html` and `paste` continue to work
   > as aliases for the `implement` subcommand. Existing scripts and
   > muscle memory will keep working.

5. **Present** the HTML with a `computer://` link so the user can open it
   directly. Tell them: for each script, click **Copy XML**, then in
   FileMaker open the target script in Script Workspace and ⌘V / Ctrl+V.
   For manual layout / schema steps, follow them in order — the page
   numbers them so it's easy to track progress.

## Spec JSON shape (author mode)

```json
{
  "meta": {
    "title": "Fungal Picker Scripts",
    "author": "Xandon",
    "date": "2026-05-20",
    "notes": "Paste order matters: Open → Toggle → Add → Cancel."
  },
  "scripts": [
    {
      "name": "Fungal Picker — Open Card Window",
      "called_from": "Button on Mold Air DE",
      "steps": [
        { "type": "comment", "text": "Open the picker as a card window." },
        { "type": "if", "calc": "Get ( layoutTableName ) ≠ \"Mold Layers\"" },
        { "type": "show_dialog", "title": "\"Picker\"",
          "message": "\"Open from Mold Air DE.\"" },
        { "type": "exit_script" },
        { "type": "end_if" },
        { "type": "set_variable",
          "name": "$$FUNGAL_PICKER_LAYER_ID",
          "calc": "Mold Layers::Layer ID" },
        { "type": "new_card_window",
          "name": "\"Pick Fungal Species\"",
          "layout": "Fungal Species_Air Fungal Spores - Picker",
          "height": 700, "width": 540 }
      ]
    }
  ]
}
```

### Step types

Each step is `{"type": "<step_type>", …type-specific fields…}`. All optional
fields fall back to sensible defaults.

| `type` | Required fields | Optional |
| --- | --- | --- |
| `comment` | — | `text`, `enabled` |
| `if` / `else_if` / `exit_loop_if` | `calc` | — |
| `else`, `end_if`, `loop`, `end_loop` | — | — |
| `exit_script` / `halt_script` | — | `calc` (exit only) |
| `set_variable` | `name`, `calc` | `rep` |
| `set_field` | `table`, `field`, `calc` | — |
| `set_field_by_name` | `table`, `field`, `target` | — |
| `insert_calculated_result` | `table`, `field`, `calc` | `select` |
| `show_dialog` | `title`, `message` | `two_buttons` |
| `set_error_capture` / `allow_user_abort` | — | `on` |
| `go_to_layout` | `layout` | — |
| `go_to_record` | — | `target` (First/Last/Previous/Next/ByCalculation) |
| `enter_find_mode` / `enter_browse_mode` | — | `pause` |
| `perform_find`, `show_all_records` | — | — |
| `new_record`, `commit_records`, `delete_record`, `delete_portal_row` | — | `no_dialog`, `skip_validation` |
| `new_card_window` | `name`, `layout` | `height`, `width`, `top`, `left`, controls |
| `new_window` | `name` | `style`, `layout`, geometry, controls |
| `close_window`, `freeze_window`, `refresh_window` | — | `flush` (refresh) |
| `refresh_object`, `refresh_portal` | — | `name` |
| `perform_script` | `script` | `parameter` |
| `raw_xml` | `xml` | `pseudocode` — escape hatch when no other type fits |

The generator looks up every named reference against the DDR:

- `layout` → `layouts.name`
- `script` → `scripts.name`
- `table` + `field` → `fields.table_name` + `fields.name`
  (will also resolve via `relationships` if `table` is a TO name)

On a miss the generator fails with a "did you mean…" list of nearby names —
**do NOT silently fall back to typing names without IDs**, because paste
will then partially fail in FileMaker.

## Best practices

- **Validate references first.** Before writing a spec, confirm each field /
  layout / script you're about to reference exists in the DDR by running
  the corresponding `/fm-query` lookup.
- **Group related changes in one page.** Paste order matters when scripts
  call each other; list them in the order the user should paste. Manual
  layout / schema steps should be numbered and placed at the point in
  the sequence they need to be applied.
- **Always include a header comment block** per authored script — Purpose,
  Called From, Author, Created, Parameters — to match solution conventions.
- **Use `raw_xml` sparingly.** If you find yourself reaching for it,
  consider whether the missing step type belongs in
  `fm_step_builders.py` instead.
- **Be explicit about rollback** for schema changes — add a `notes` section
  documenting how to undo each manual step if the change needs to be
  reverted in production.

Do NOT invent script names or step types — always cross-check against the
indexed DDR via `/fm-query`.
