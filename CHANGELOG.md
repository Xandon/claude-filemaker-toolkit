# Changelog

All notable changes to the FileMaker Toolkit plugin are documented in this
file. The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.4] — 2026-05-28

### Added
- **`/fm-implement` slash command** — replaces `/fm-paste-html` with a broader
  remit. Builds a paste-ready implementation package for FileMaker changes:
  Copy-XML buttons for new and existing scripts, plus ordered manual steps for
  layout / schema / relationship / security changes that FileMaker cannot
  paste directly.
- `commands/fm-implement.md` documents the expanded scope, adds Manual-steps
  and Notes sections to the "what an implementation package can contain"
  table, and nudges authors to think about rollback for schema changes.
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

[0.2.4]: https://github.com/Xandon/claude-filemaker-toolkit/releases/tag/v0.2.4
[0.2.3]: https://github.com/Xandon/claude-filemaker-toolkit/releases/tag/v0.2.3
[0.1.0]: https://github.com/Xandon/claude-filemaker-toolkit/releases/tag/v0.1.0
