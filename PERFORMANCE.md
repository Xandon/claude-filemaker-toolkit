# Reviewing the Plugin for Efficiency

This guide explains how to verify that the FileMaker Toolkit plugin is performing well — both in raw toolkit execution speed and in how Claude uses it during conversations.

**Applies to version 0.3.0** (four slash commands: `/fm-setup`, `/fm-query`, `/fm-review`, `/fm-implement`; streaming DDR indexer).

## 1. Validate the plugin structure

Before anything else, confirm the plugin manifest and layout are valid:

```bash
claude plugin validate ${CLAUDE_PLUGIN_ROOT}/.claude-plugin/plugin.json
```

Fix any errors or warnings before proceeding.

## 2. Benchmark the indexer

The v0.3.0+ indexer streams the DDR XML — peak memory is bounded by the
largest single catalog / script block, not the whole document. It should
process a 100 MB DDR XML in under 3 seconds on a modern laptop and stay
well under 500 MB RSS on a RAM-constrained sandbox. To benchmark:

```bash
time python ${CLAUDE_PLUGIN_ROOT}/scripts/fm_parser.py index solutions/LAYER/LAYER.xml --db /tmp/test.db
```

Every `index` run also prints a `Peak RSS: N MB` line at the end (POSIX
only). For a more precise number use `/usr/bin/time -v` (Linux) or
`/usr/bin/time -l` (macOS) and read `Maximum resident set size`.

Expected ballpark for a "large" solution:

| XML size | Scripts | Steps | Expected index time | DB size | Streaming peak RSS |
|---|---|---|---|---|---|
| 20 MB   | ~200 | ~5,000  | <1 s   | ~1 MB | ~30 MB   |
| 100 MB  | ~600 | ~15,000 | 1–2 s  | ~5 MB | ~120 MB  |
| 200 MB  | ~800 | ~25,000 | 2–4 s  | ~8 MB | ~250 MB  |

Real-world reference: on the ILCrop 187 MB UTF-16 export (125 tables,
4,046 fields, 845 scripts, 25,970 steps, 483 layouts, 624 relationships,
230 value lists, 162 custom functions, 4,309 CF cross-references), the
streaming indexer completes in a few minutes on the ~4 GB Cowork sandbox
under 500 MB peak RSS.

If the indexer takes significantly longer:
- Check that `.fm_db_cache/` is on local disk, not a network or mounted filesystem
- Confirm `FM_DB_CACHE` isn't pointing to a slow location
- Large CF cross-reference counts (>5,000) add parsing time — that's expected

If peak RSS is *higher* than expected (>~1.5× the size in the table
above), you're probably on the legacy DOM parser. Confirm you're on
v0.3.0+ (`python fm_parser.py --version` if wired, or check
`.claude-plugin/plugin.json`). The DOM path is still callable via
`index_file(..., use_dom=True)` for parity comparison but should never
be the default.

## 3. Benchmark query latency

All queries should return in under 100ms because they hit indexed SQLite columns. Test with:

```bash
time python ${CLAUDE_PLUGIN_ROOT}/scripts/fm_manage.py query LAYER summary
time python ${CLAUDE_PLUGIN_ROOT}/scripts/fm_manage.py query LAYER scripts
time python ${CLAUDE_PLUGIN_ROOT}/scripts/fm_manage.py query LAYER script 100
time python ${CLAUDE_PLUGIN_ROOT}/scripts/fm_manage.py query LAYER search "Import"
```

If any command takes more than 500ms on a fresh shell, investigate:
- Python startup overhead (~80–150ms is normal)
- SQLite cold cache (first query after reboot is slower)
- Full-text search on `search` with very common terms

## 4. Test the slash commands in a fresh Cowork session

Restart Cowork, create a new chat, and walk through each command in order:

1. `/fm-setup` with a known XML file → verify the summary output matches `fm_manage.py query <name> summary`
2. `/fm-query <name> hotspots` → verify you get a ranked list
3. `/fm-query <name> script "<known script>"` → verify the human-readable output matches expectations
4. `/fm-review` on a known-buggy script → verify the HTML file is generated and opens correctly
5. `/fm-implement` on either an existing script (extract mode) or a small new-script spec (author mode) → verify the resulting HTML opens, the **Copy XML** button works, and pasting the clipboard into FileMaker Script Workspace materialises the steps cleanly. Also verify the legacy subcommand names still resolve (`fm_manage.py paste-html …` and `fm_manage.py paste …`).

For each command, Claude should:
- Run the actual toolkit (no fabricated output)
- Use file paths relative to the current project folder
- Not hardcode any session-specific paths

## 5. Test the skill's trigger accuracy

The `filemaker-xml-analyzer` skill is designed to auto-load when the user mentions FileMaker, DDR XML, scripts, layouts, etc. Test by starting fresh sessions and asking things like:

- "Can you look at this FileMaker script?" → skill should load
- "Help me with this XML file" (with a DDR XML attached) → skill should load
- "I have a performance issue in LAYER.fmp12" → skill should load
- "What is FileMaker?" → skill should NOT load (generic question)

If the skill is loading on unrelated queries, tighten the description. If it's missing obvious triggers, add example phrases.

## 6. Test the review template

The HTML review template is the biggest single file in the plugin. Review its size and behavior:

```bash
wc -l ${CLAUDE_PLUGIN_ROOT}/templates/review_template.html
ls -lh ${CLAUDE_PLUGIN_ROOT}/templates/review_template.html
```

Generate a review for a large script and check that:
- The output HTML file is <1 MB (otherwise it's loading too much)
- It opens in <500ms in a browser
- Syntax highlighting works
- Custom function chips render and scroll-to-usage works
- One-click XML copy actually copies clipboard-compatible XML

## 7. Check for common regressions

| Symptom | Likely cause |
|---|---|
| "Permission denied" on `.fm_db_cache/` | Project folder is read-only; set `FM_DB_CACHE` to a writable path |
| "Database is locked" | SQLite on a mounted filesystem; fall back to `~/.cache/filemaker-toolkit/db_cache` |
| Parser errors on `\x10` control chars | Older parser build; the current build sanitizes these |
| Custom functions count = 0 | Wrong CF catalog tag name (singular vs plural) — the parser checks both |
| CF cross-references count = 0 | Regex word-boundary failing on unusual CF names (underscores, etc.) |
| Review HTML shows no findings | JSON injection failed; check `${CLAUDE_PLUGIN_ROOT}/scripts/fm_review_gen.py` handles `</script>` escapes |

## 8. Profile Claude's context usage

When Claude uses the plugin, it should avoid pulling entire scripts into context unnecessarily. Watch for these efficiency signs:

- **Good**: Claude runs `script <name>` and reads the output, then runs a targeted follow-up
- **Bad**: Claude reads the whole DB file or XML file via the Read tool instead of querying
- **Bad**: Claude fabricates step numbers instead of running a command

If you see Claude doing the wrong thing, tighten the command descriptions in `commands/*.md` to be more directive.

## 9. Continuous checks

After any edit to the toolkit:

```bash
# Quick smoke test
python ${CLAUDE_PLUGIN_ROOT}/scripts/fm_manage.py list
python ${CLAUDE_PLUGIN_ROOT}/scripts/fm_manage.py index path/to/known.xml --name smoke_test
python ${CLAUDE_PLUGIN_ROOT}/scripts/fm_manage.py query smoke_test summary
python ${CLAUDE_PLUGIN_ROOT}/scripts/fm_manage.py query smoke_test script 1
```

If any step fails, you have a regression.

## 10. Keep the SKILL.md lean

SKILL.md is loaded into context every time the skill triggers. Keep it under 3,000 words. Move detailed content into `references/` and load it on demand via the Read tool. To check current word count:

```bash
wc -w ${CLAUDE_PLUGIN_ROOT}/skills/filemaker-xml-analyzer/SKILL.md
```

If it's over 3,000, trim example blocks and move step-type details into `references/fm_step_reference.md`.
