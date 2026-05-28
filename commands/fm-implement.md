---
description: Package the feature/change you and the user have been designing into a paste-ready HTML implementation guide
---

`/fm-implement` is the **end of a design conversation**, not the start of
one. By the time the user invokes it, the workflow looks like this:

1. The user ran `/fm-setup` earlier and the FileMaker solution is indexed.
2. The user asked Claude a general feature / change question:
   *"I want to add a fungal species picker on the Mold Layers layout."*
   *"Refactor the Import script so it commits inside the loop."*
   *"Add a Notes field to the Visits table and surface it on the
   Inspection detail layout."*
3. Claude used `/fm-query` against the indexed DDR to ground the
   proposal in the user's actual fields, layouts, scripts, table
   occurrences, and relationships — and laid out everything that would
   need to change: new scripts, edits to existing scripts, layout
   adjustments, schema changes.
4. The user reviewed the plan, asked follow-ups, added details ("the
   picker has to be modal", "skip the commit refactor in the legacy
   Import_v1 path"), and Claude iterated.
5. Now the user is satisfied with the design and says `/fm-implement`.

**Your job at this point** is to package the agreed plan as a single
self-contained HTML deliverable the user can open and work through
top-to-bottom in FileMaker. Every script on the page gets a **Copy XML**
button that puts FM 18+ clipboard XML on the clipboard, ready to paste
straight into Script Workspace — no MBS plugin needed. Anything the
generator cannot paste (layout edits, new fields, relationship changes,
security tweaks) is rendered as numbered manual steps in the order the
user should apply them.

## What goes on the page

| Section | What it is | Pulled from |
| --- | --- | --- |
| **Header notes** | Goal of the change, rollback plan, testing checklist, paste order | The design conversation |
| **Manual steps** | Numbered instructions for layout / schema / relationship / security work | What you and the user agreed had to change in FileMaker's UI |
| **New scripts** | Author-mode: scripts Claude designed during the conversation | The spec JSON you write in step 3 |
| **Existing scripts** | Extract-mode: scripts pulled verbatim from the indexed DDR | The user's solution, via `--script <name\|id>` |

One HTML page mixes all four freely. Order matters when scripts call
each other — list them in the order the user should paste.

## Workflow

1. **Sanity check the prerequisites.** The solution must be indexed
   (i.e. `/fm-setup` has already run for it). If for some reason it
   hasn't, run `/fm-setup` first — `/fm-implement` cannot guess at
   field, layout, or script names without it.

2. **Summarize the agreed plan back to the user before generating.**
   In one short message, restate what scripts you'll author, which
   existing scripts you'll extract, and what manual steps you'll
   include. This catches any mismatch between your understanding and
   theirs before you build a 1 MB HTML deliverable. Skip this step
   only if the user explicitly said "just generate it".

3. **Write the spec JSON** capturing the new scripts and manual steps.
   Save to `solutions/<solution>/output/<feature-name>.spec.json` (or
   under `reviews/` if the user prefers). See "Spec JSON shape" below
   and `examples/picker_spec_example.json` for a worked reference.
   Validate every field / layout / table / script name against the
   indexed DDR using `/fm-query` **before** putting it in the spec —
   the generator will reject unknown names with a "did you mean…" list,
   but it's faster to catch it now.

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
   directly. Tell them: work through the page top to bottom — for each
   script card, click **Copy XML**, switch to FileMaker, open the target
   script in Script Workspace, and ⌘V / Ctrl+V. For manual steps, do
   them in order — the page numbers them so it's easy to track progress.
   Close the loop by asking if anything else needs adjusting before
   they consider the change shipped.

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
