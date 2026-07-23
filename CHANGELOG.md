# Changelog

All notable changes to the FileMaker Toolkit plugin are documented in this
file. The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.3.5] — 2026-07-23

### Fixed
- **`fm_manage.py index` printed "Database saved to:" twice per solution.**
  The first line was `.fm_db_cache/<name>.db` (the temp cache path);
  the second was `solutions/<name>/<name>.db` (the final location).
  In fact `fm_manage.py` copies the DB from the cache to the solutions
  folder, unlinks the cache copy, and prints its own final-location
  message — so the first path was stale by the time the user saw it,
  the DB was NOT actually in two places, and reading the output made
  it look like both files existed. The stale line is now filtered
  out of the fm_parser subprocess output before the final message
  prints. Only one authoritative "Database saved to:" line per run.

### Changed
- **Per-Layout and per-FieldCatalog streaming in `fm_parser.py`.**
  Previously, `LayoutCatalog` and `FieldsForTables` were handled as
  whole catalogs on their end events: iterparse accumulated every
  child element under those containers before the handler ran, so
  peak RSS scaled with the size of the largest catalog rather than
  the largest single child. On a layout-heavy real-world solution
  (SAMPLES: 248 MB XML, 526 layouts, 4,013 fields) this pushed peak
  RSS to **868 MB** — well above the < 500 MB target for the
  streaming indexer.

  Fix (mirrors the existing per-Script pattern inside `StepsForScripts`):
    - Extracted `_handle_single_layout` from `_handle_layout_catalog`
      and `_handle_single_field_catalog` from
      `_handle_fields_for_tables` (both retained for the DOM fallback
      path).
    - Added `in_layout_catalog` and `in_fields_for_tables` state flags
      to the iterparse loop.
    - The loop now dispatches on Layout and FieldCatalog end events
      inside their respective catalogs, calls the per-child handler,
      and clears the element immediately. The enclosing catalog's own
      end event just resets the flag and clears the (now empty)
      container.

  Expected: peak RSS on layout-heavy DDRs (500+ layouts) drops from
  "all layouts in memory" to "one biggest layout in memory", which
  should bring SAMPLES from 868 MB to the 200–400 MB range and keep
  other files under the 500 MB target regardless of layout count.
  Field-heavy solutions (MetalsQC: 6,629 fields; SAMPLES: 4,013)
  benefit less because individual fields are smaller than layouts,
  but the pattern is symmetric and costs nothing.

- **Parity verified in-repo** (PBS Demo — Maps Widget, 4.2 MB XML):
  full row-count parity across all 13 tables between streaming and
  DOM paths; deep parity 100/100 on script_steps, 7/7 on layouts,
  37/37 on fields (all row content byte-identical).

## [0.3.4] — 2026-07-23

### Fixed
- **`fm_index_wrapper.sh` failed on macOS's default bash 3.2 with
  `NAME_ARGS[@]: unbound variable`.** The previous version accumulated
  the optional `--name <solution>` argument into a bash array
  (`NAME_ARGS=()`) and expanded it as `"${NAME_ARGS[@]}"` at the
  python invocation. On bash 4.4+ that expands to nothing for an empty
  array, but on bash 3.2 — which is still what `#!/usr/bin/env bash`
  resolves to on stock macOS — the same expansion under `set -u`
  raises "unbound variable" and aborts the script. Because that abort
  happens *after* the wrapper prints its `Plugin / Python / Project
  dir / XML file / Solution` header, users running a batch loop saw
  the header for each file followed by the error, and none of the
  DDRs actually got indexed (real-world report: a 10-DDR / 2.7 GB
  batch printed 10 error lines, produced 0 indexes).

  Fix: dropped the array entirely. `SOL_NAME_OVERRIDE` is now a simple
  string; the python invocation branches on whether the string is
  empty, calling either
  `python3 fm_manage.py index <xml> --name <override>` or
  `python3 fm_manage.py index <xml>`. Portable across every bash from
  3.2 onwards, and readable.

  Regression-tested in-repo: end-to-end with and without `--name`,
  and a self-check that greps the packaged wrapper to ensure the
  offending `NAME_ARGS[@]` expansion is absent from live code (it
  appears once in an explanatory comment describing what was
  removed — that's fine).

### Changed
- No plugin runtime or Python changes. Wrapper-only fix.

## [0.3.3] — 2026-07-23

### Fixed
- **`fm_index_wrapper.sh` silently exited on first run when `nullglob`
  was off (its default state).** Under `set -euo pipefail`, the
  `SHOPT_RESET=$(shopt -p nullglob)` line intended to save the shopt
  state for restoration returns exit code 1 whenever `nullglob` is
  off — which is the default in a fresh interactive shell. That
  non-zero return killed the wrapper before it printed its own
  `Plugin: …` header, leaving the user with just their outer loop's
  `!!! FAILED: …` fallback and no diagnostic. Reproduced in-repo:
  running the wrapper with `HOME=` pointed at an empty directory
  used to exit silently; it now prints the full "Could not locate
  fm_manage.py" block.

  Fix: replaced the `shopt -p` / `shopt -s` / restore dance with a
  subshell that enables `nullglob` locally, expands the candidate
  globs via `printf '%s\n'`, and pipes the results to a `while
  IFS= read -r candidate` loop in the outer script. Glob expansion
  stays isolated to the subshell, no shopt state leaks, and none
  of the exit codes involved can trip `set -e`.

  Regression tests exercised in-repo: `bash -n` syntax, `--help`
  output, missing-file error path, no-candidates auto-detect
  (prints the ERR block, exits 1 with a clear message), and
  `FM_MANAGE_PATH` override still resolving to a working indexer.

### Changed
- No plugin runtime or Python changes. Wrapper-only fix.

## [0.3.2] — 2026-07-19

### Added
- **`scripts/fm_index_wrapper.sh`** — a single-file bash wrapper that
  finds the installed plugin's `fm_manage.py` and runs `index` +
  `query summary` from the current directory. When the native-Terminal
  path is required for a large DDR, this is the ONE file that lands in
  the user's project folder — no Python files need to be copied.

  Auto-detection order:
    1. `$FM_MANAGE_PATH` (explicit override)
    2. `~/Library/Application Support/Claude/local-agent-mode-sessions/*/*/rpm/plugin_*/scripts/fm_manage.py`
    3. `~/Library/Application Support/Claude/plugins/*/scripts/fm_manage.py`
    4. `~/.filemaker-toolkit/scripts/fm_manage.py`

  Each candidate is grep-verified as filemaker-toolkit before being
  used, so a same-named script from another plugin can't be picked up
  accidentally. `$FM_PYTHON` overrides the interpreter (default
  `python3`). `$FM_PROJECT_DIR` overrides where `solutions/` and
  `.fm_db_cache/` land (default: current working directory). `--name`
  argument overrides the solution name (default: XML basename).

### Changed
- **`commands/fm-setup.md` step 0 rewritten** to prefer the wrapper
  over copying the full `scripts/` directory. Claude now copies just
  the one `.sh` file into the user's connected folder and hands them
  `./fm_index_wrapper.sh "<file>.xml"`. The full `scripts/` copy path
  stays as a documented fallback for the case where the wrapper can't
  find the plugin (e.g. non-standard install location) — with an
  `FM_MANAGE_PATH` escape hatch called out explicitly.
- No plugin runtime changes. The wrapper is a shell script only; the
  plugin still runs with pure standard-library Python.

## [0.3.1] — 2026-07-17

### Changed
- **Large-file policy in `/fm-setup` — native Terminal is now the only allowed path.**
  Step 0 of `commands/fm-setup.md` was rewritten to remove the cloud-run
  escape hatch entirely. Previously the doc offered Claude two options for
  large DDRs (gzip-and-transfer to a cloud sandbox, or native Terminal on
  the user's machine). Cloud runs are no longer permitted for large files
  under any circumstance, so Claude will no longer offer or suggest that
  path.
- **New trigger condition.** The old "> 50 MB AND RAM < 4× file size"
  heuristic is replaced by a hard rule: if the XML file is **> 50 MB**
  OR the current session is a cloud / Cowork sandbox and the file lives on
  the user's device, the indexer runs on the user's machine via native
  Terminal `python3`. Available RAM is intentionally excluded — a big
  cloud sandbox with plenty of RAM is still not allowed to index the file
  because the file must not move.
- **Explicit guardrail added.** Step 0 now carries a hard-rule line:
  *"NEVER stage, upload, gzip-and-transfer, or otherwise move a large DDR
  XML into a cloud sandbox to index it. NEVER run the indexer over the
  device bridge. Large DDRs stay on the user's machine and are indexed by
  native Terminal `python3`, producing the `solutions/` index in the
  user's local project folder."*
- Native-run flow is unchanged: commit `scripts/` to a connected folder if
  needed, hand the user the paste-ready `python3 fm_manage.py index …
  && … query <name> summary` command, wait for confirmation, then verify
  the resulting `.fm_db_cache/<name>.db` and summary counts over the
  connected folder.

### Motivation
- Cloud-run indexing of a device-resident DDR requires moving the file
  across the sandbox bridge, which is slow, error-prone, and exposes the
  full DDR (schema, script logic, client-identifiable strings) to the
  cloud runtime. Native Terminal `python3` on the user's own machine
  avoids all three.
- The streaming indexer landed in 0.3.0 already makes in-sandbox indexing
  of moderately-large DDRs safe on RAM; this change tightens the
  policy for anything meaningfully large, independent of RAM.

## [0.3.0] — 2026-07-16

### Fixed
- **True streaming DDR indexer.** `fm_parser.py` no longer holds the whole
  document in memory. A real-world 187 MB UTF-16 DDR from ILCrop
  (`125 tables / 4,046 fields / 845 scripts / 25,970 steps / 483 layouts /
  624 relationships / 230 value lists / 162 custom functions`) previously
  peaked at 4–8 GB RSS in the ~4 GB Cowork sandbox and hung indefinitely.
  The new path targets < 500 MB peak on the same file. Two stages, both
  bounded by chunk / catalog size rather than document size:

  1. **Stream-transcode to UTF-8.** The source file is read in 1 MiB
     chunks through `codecs.getincrementaldecoder(<encoding>)`, invalid
     XML 1.0 control characters are stripped with a precomputed
     `str.translate` table (much cheaper than regex over hundreds of MB),
     the XML declaration is rewritten from `encoding="UTF-16"` to
     `encoding="UTF-8"`, and the result is written to a
     `tempfile.NamedTemporaryFile`. The temp file is unlinked in a
     `finally` block.
  2. **iterparse dispatch.** The temp file is walked with
     `ET.iterparse(events=('start','end'))`. On each catalog `end`
     event (`FieldsForTables`, `ValueListCatalog`, `RelationshipCatalog`,
     `ScriptCatalog`, `LayoutCatalog`, `ExternalDataSourceCatalog`,
     `CustomFunctionCatalog` / `CustomFunctionsCatalog`) and on each
     inner `Script` end event within `StepsForScripts`, the fully-built
     element is dispatched to a per-catalog handler and then cleared,
     so peak memory tracks the single largest catalog / script block —
     not the whole document. State flags (`in_add_action`,
     `in_steps_for_scripts`) restrict extraction to the top-level
     `<AddAction>` container, matching the DOM parser's behaviour on
     diff-shaped DDRs that also carry `<ModifyAction>` / `<DeleteAction>`.

- Verified: byte-identical row counts and step content (`raw_xml`,
  `human_readable`) between the streaming and DOM paths on two real
  FileMaker exports (PBS_Widget: 3 tables, 18 scripts, 285 steps;
  PBS Demo — Maps Widget: 1 table, 31 scripts, 626 steps). Streaming
  peak RSS was 17 MB on both, vs 23 MB / 30 MB for the DOM path — the
  streaming path is roughly flat while the DOM path scales with file
  size.

### Added
- **Per-catalog handler functions in `fm_parser.py`**. The inline
  extraction logic that used to live in `index_file` is now factored
  into eight module-level handlers (`_handle_fields_for_tables`,
  `_handle_value_list_catalog`, `_handle_relationship_catalog`,
  `_handle_script_catalog`, `_handle_layout_catalog`,
  `_handle_external_data_source_catalog`,
  `_handle_custom_function_catalog`, `_handle_script_block`) plus a
  shared `_build_cf_cross_references` for the CF cross-reference pass
  and `_print_summary_and_close` for the finalize path. Same SQL,
  same schema, unchanged behaviour — just reusable and testable.
- `parse_xml_dom()` — the legacy whole-file-in-memory parser, kept as
  a fallback and used by `index_file(..., use_dom=True)` for parity
  checks.
- `index_file(xml_path, db_path, use_dom=False)` new parameter selects
  streaming (default) or DOM. External callers keep working — the
  signature is backwards-compatible.
- **Peak-RSS reporting.** `_print_summary_and_close` prints `Peak RSS: N MB`
  after every `index` run (POSIX only; skipped on Windows). Uses
  `resource.getrusage(RUSAGE_SELF).ru_maxrss` with per-platform
  normalisation (macOS reports bytes, Linux reports KiB).
- **Large-file guard in `/fm-setup`.** New step 0 tells Claude to check
  the XML file size and available RAM before indexing. If the file is
  > 50 MB AND available RAM is less than 4× the file size, Claude is
  now instructed to offer the user two escape hatches instead of
  grinding through in-sandbox:
  1. Cloud session — gzip the DDR (compresses 10–20×) and re-run
     `/fm-setup` from a cloud session with more RAM.
  2. Native run — hand the user a paste-ready Terminal command that
     runs the pure-stdlib scripts locally (no `pip install` required),
     then verify the resulting index over the shared folder.

  With the streaming indexer landed, this guard should rarely trigger,
  but it stays as a safety net for older installs and pathological
  files.

### Changed
- `plugin.json` version `0.2.5` → `0.3.0`.
- `PERFORMANCE.md`: memory characteristics updated to reflect the
  streaming path.
- No new dependencies. Scripts remain pure standard library (they get
  copied to user machines and run with the system `python3`).

## [0.2.5] — 2026-05-28

### Added
- **Structured implementation-notice block.** The notice block at the top
  of an `/fm-implement` HTML page can now be populated from first-class
  `meta.*` fields instead of a single free-form `meta.notes` string.
  Renders as a subtitle card, a pill row of preconditions, numbered
  manual-step cards (each with `title`, `body`, optional `<pre>` `code`
  block, and a green ✓ `done_when` line), a bottom-left "reuse" card,
  and a bottom-right rollback list with optional footnote — instead of
  the legacy amber free-form callout.
- New `meta` fields: `subtitle`, `prereqs`, `manual_steps`, `reuse`,
  `rollback`, `rollback_note`. All optional. If none are set, the
  renderer falls back to `meta.notes` exactly as before — existing
  specs keep rendering with no changes.
- **Inline markdown-lite** in prose fields (`subtitle`, `body`,
  `done_when`, list items, `reuse.*` prose): `` `code` `` → `<code>`,
  `**bold**` → `<b>`, `*italic*` → muted dotted-underline (suits FM
  menu items / contextual hints). `code` blocks
  (`manual_steps[*].code`, `reuse.code`) are HTML-escaped only —
  Markdown is not applied so calculation expressions render literally.
- **`--notice-html-file <path>`** CLI flag on `fm_manage.py implement`
  (and on `fm_paste_html_gen.py` directly) — power-user escape hatch
  that injects raw HTML into the notice block with no escaping. Use
  only when the structured schema can't express what you need; it
  beats both the structured renderer and `meta.notes` in precedence.
- New `_md_inline()` and `_render_structured_notice()` helpers in
  `scripts/fm_paste_html_gen.py`; the `spec` branch in
  `generate_paste_html()` tries the structured renderer first and
  falls back to the legacy `meta.notes` path.
- `.impl-*` CSS classes hosted in `templates/paste_template.html` so
  spec authors don't need to ship CSS inline; a `:has()` rule
  neutralises the legacy amber notice container when structured
  content is present.

### Changed
- `commands/fm-implement.md`: replaced the spec example with one that
  exercises the new structured fields, and added a "Meta fields — the
  implementation notice block" reference table covering the field
  shapes, `manual_steps[*]` schema, and the markdown-lite rules.
- `skills/filemaker-xml-analyzer/SKILL.md`: new "Notice block: manual
  steps & rollback" subsection under "Designing & Shipping Changes",
  with the Portal Snapshot worked example and the markdown-lite
  reference. Tells Claude to prefer structured fields over the legacy
  `meta.notes` for any change that spans more than a single script.
- `plugin.json`: version `0.2.4` → `0.2.5`.

### Backward compatibility
- Specs that only use `meta.notes` continue to render via the legacy
  free-form amber-callout path. The structured renderer is opt-in:
  it only activates when at least one structured field is set.

### Verified
- End-to-end run of `fm_manage.py implement` against the converted
  Portal Snapshot spec (using the new structured fields) produced the
  polished card / numbered-step layout that the design preview
  established.

## [0.2.4] — 2026-05-28

### Added
- **`/fm-implement` slash command** — replaces `/fm-paste-html` with a broader
  remit and a clearer mental model: it's the **end of a design conversation**,
  not the start of one. The intended flow is:
  1. User runs `/fm-setup` to index their solution.
  2. User asks Claude a feature- or change-shaped question
     ("add a Notes field to Visits and surface it on the detail layout").
  3. Claude grounds the proposal in the indexed DDR — telling the user
     exactly which scripts will be added or changed, which layouts to
     edit, which fields/tables/relationships to add — and the two iterate.
  4. When the user is satisfied, `/fm-implement` packages the agreed plan
     as a single self-contained HTML deliverable: Copy-XML buttons for
     new and existing scripts, plus ordered manual steps for the
     layout / schema / relationship / security work FileMaker cannot
     paste directly.
- `commands/fm-implement.md` re-framed around the above flow. The
  docstring at the top now explicitly walks Claude through the
  conversation-first lifecycle and tells it to summarize the plan back
  to the user before generating, so the deliverable always matches the
  user's expectations.
- Top-level `CHANGELOG.md` (this file).
- `examples/picker_spec_example.json` (synced from upstream) — full reference
  spec for author-mode scripts.

### Changed
- `fm_manage.py` subcommand `paste-html` renamed to `implement`. The legacy
  names `paste-html` and `paste` remain as `argparse` aliases for backward
  compatibility — anything that already called the old names keeps working.
- Default output filename for the subcommand: `scripts.html` → `implementation.html`.
- `plugin.json`: version `0.2.3` → `0.2.4`; description updated to mention
  paste-ready implementation packages; keywords list: `paste-html` removed,
  `implement` and `deployment` added.
- `README.md`: tagline updated to "shipping changes to" instead of "modifying";
  "What It Does" / Installation / Project Layout / Quick Start / Commands /
  Running Scripts Directly / HTML Output sections refreshed for the new
  command and the broader scope. MBS-plugin requirement softened — the
  paste-back path now uses native FM 18+ clipboard format and no longer
  requires MBS.
- `PERFORMANCE.md`: new header noting v0.2.4, and section 4 (slash-command
  smoke test) extended with a step for `/fm-implement` plus a check that the
  legacy `paste-html` / `paste` subcommand aliases still resolve.
- `skills/filemaker-xml-analyzer/SKILL.md`: description and command-count
  updated; "Authoring & Delivering" section retitled to "Authoring &
  Delivering an Implementation Package", references the new slash command.

### Removed
- `commands/fm-paste-html.md` — the deprecation pointer file. It was
  showing up in the Cowork plugin panel as a second slash command with
  description "(Renamed) Now /fm-implement", which was just visual noise.
  Users now see only `/fm-implement` in their skills list.

### Migration notes
- Pre-existing review JSONs and scripts that called `python fm_manage.py
  paste-html …` continue to work unchanged.
- If you have anything pointing at the old default output filename
  (`scripts.html`), either update the path or pass `-o scripts.html`
  explicitly.

## [0.2.3] — 2026-05-22 (upstream)

The repo's initial import was synced to the live plugin at this version. The
upstream work between 0.1.0 and 0.2.3 included:

### Added
- `commands/fm-paste-html.md` — slash command for building a paste-ready
  HTML page of FileMaker scripts with Copy-XML buttons (FM 18+ clipboard
  format, no MBS plugin required).
- `scripts/fm_paste_html_gen.py` — generator for the paste-html page.
- `scripts/fm_step_builders.py` — reusable step-template helpers used by
  the generator.
- `templates/paste_template.html` — self-contained HTML template for the
  paste-html output.
- `examples/picker_spec_example.json` — full reference spec.
- Independent implementations of the missing-fix-XML warning system in
  `fm_review_gen.py` and a "Copy Fix Text" / disabled-button UI fallback
  in `review_template.html`. These supersede the equivalent fixes added
  in earlier 0.1.0 patch commits.

### Changed
- Significant refactor of `fm_review_gen.py` toward a simpler generation
  pipeline.
- Slim-down of `fm_xml_gen.py`.
- Internal updates to `fm_diagnostics.py`, `fm_manage.py`, `fm_parser.py`,
  `fm_query.py`.
- Updates to `commands/fm-query.md`, `commands/fm-review.md`,
  `commands/fm-setup.md`, and `skills/filemaker-xml-analyzer/SKILL.md`.
- `plugin.json`: version `0.1.0` → `0.2.3`; description and keywords
  updated to reflect paste-ready HTML script delivery.

### Removed
- `scripts/fm_diff.py` and `scripts/fm_graph.py` were dropped from the
  upstream tree.

## [0.1.0] — 2026-04-09

### Added
- Initial public version of the FileMaker Toolkit plugin.
- DDR XML indexer (`scripts/fm_parser.py`) — parses a FileMaker DDR XML
  export into a SQLite database in 1–3 seconds.
- Query CLI (`scripts/fm_query.py` via `scripts/fm_manage.py query`) —
  script analysis, schema exploration, custom-function indexing,
  cross-reference lookup, full-text search.
- Diagnostics (`scripts/fm_diagnostics.py`) — hotspots, slow patterns,
  orphans, duplicates, dead code, anti-patterns, health scorecard.
- Interactive code review (`scripts/fm_review_gen.py` +
  `templates/review_template.html`) — self-contained HTML with
  syntax-highlighted steps, severity-rated findings, before/after diffs,
  custom-function chips, and one-click XML copy.
- Three slash commands (`/fm-setup`, `/fm-query`, `/fm-review`).
- Skill (`filemaker-xml-analyzer`) with reference docs covering DDR XML
  structure, step types, relationship map, and FM step catalog.

[0.3.5]: https://github.com/Xandon/claude-filemaker-toolkit/releases/tag/v0.3.5
[0.3.4]: https://github.com/Xandon/claude-filemaker-toolkit/releases/tag/v0.3.4
[0.3.3]: https://github.com/Xandon/claude-filemaker-toolkit/releases/tag/v0.3.3
[0.3.2]: https://github.com/Xandon/claude-filemaker-toolkit/releases/tag/v0.3.2
[0.3.1]: https://github.com/Xandon/claude-filemaker-toolkit/releases/tag/v0.3.1
[0.3.0]: https://github.com/Xandon/claude-filemaker-toolkit/releases/tag/v0.3.0
[0.2.5]: https://github.com/Xandon/claude-filemaker-toolkit/releases/tag/v0.2.5
[0.2.4]: https://github.com/Xandon/claude-filemaker-toolkit/releases/tag/v0.2.4
[0.2.3]: https://github.com/Xandon/claude-filemaker-toolkit/releases/tag/v0.2.3
[0.1.0]: https://github.com/Xandon/claude-filemaker-toolkit/releases/tag/v0.1.0
