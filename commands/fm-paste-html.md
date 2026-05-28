---
description: Build a paste-ready HTML page of FileMaker scripts (Copy-XML buttons)
---

The user wants a self-contained HTML page where each FileMaker script is shown
with a Copy XML button. Clicking the button puts clipboard XML (FM 18+ format)
on their clipboard so they can paste it straight into Script Workspace — no
MBS plugin needed.

There are two modes; one HTML page can mix them freely:

| Mode | Input | Use when |
| --- | --- | --- |
| **Extract** | Existing script name or id from an indexed solution | Re-pasting a known script (different file, branch, or just for documentation) |
| **Author** | A JSON spec describing *new* scripts | Claude has just designed scripts and needs to ship them as paste-ready XML |

## Workflow

1. **Confirm the solution is indexed.** The HTML generator reads the SQLite
   `.db` produced by `/fm-setup`. If the user hasn't indexed it, run
   `/fm-setup` first.

2. **Decide what's on the page.** Ask the user which existing scripts to
   extract (if any) and what new scripts to author. For author mode, you
   may need to discover field / layout / TO names — run
   `/fm-query <solution> field <pattern>`,
   `/fm-query <solution> layout <pattern>`,
   `/fm-query <solution> table <name>` first.

3. **Write the spec JSON** (author mode only). Save it to
   `solutions/<solution>/reviews/<name>.json` or
   `solutions/<solution>/output/<name>.spec.json` — see "Spec JSON shape"
   below, and `examples/picker_spec.json` for a full reference.

4. **Run the generator:**

   ```bash
   python ${CLAUDE_PLUGIN_ROOT}/scripts/fm_manage.py paste-html <solution> \
       [--script "<name|id>"  ...]   \
       [--spec  <file.json>   ...]   \
       [--title "<page title>"]      \
       [--no-human]                  \
       [-o <output.html>]
   ```

   Default output is `solutions/<solution>/output/scripts.html`.

5. **Present** the HTML with a `computer://` link so the user can open it
   directly. Tell them: click **Copy XML**, then in FileMaker open the
   target script in Script Workspace and ⌘V / Ctrl+V.

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
- **Group related scripts in one page.** Paste order matters when scripts
  call each other; list them in the order the user should paste.
- **Always include a header comment block** per authored script — Purpose,
  Called From, Author, Created, Parameters — to match solution conventions.
- **Use `raw_xml` sparingly.** If you find yourself reaching for it,
  consider whether the missing step type belongs in
  `fm_step_builders.py` instead.

Do NOT invent script names or step types — always cross-check against the
indexed DDR via `/fm-query`.
