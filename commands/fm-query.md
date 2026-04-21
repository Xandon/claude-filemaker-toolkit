---
description: Run a query command against an indexed FileMaker solution
---

The user wants to query an indexed FileMaker solution. The argument format is `<solution> <command> [args...]`.

0. **Locate the plugin scripts.** In the Cowork sandbox, `$CLAUDE_PLUGIN_ROOT` may not be set. Discover the path first:
   ```bash
   FM_SCRIPTS=$(dirname "$(find /sessions -path '*/scripts/fm_manage.py' -print -quit 2>/dev/null)")
   ```
   Use `$FM_SCRIPTS/fm_manage.py` for all commands below. If the user's project folder is not the cwd, pass `--project-dir <path>`.

1. **Identify the solution.** Partial name matching is fine — run `python "$FM_SCRIPTS/fm_manage.py" --project-dir <path> list` first if the user's target is ambiguous or if you don't yet know what's indexed.

2. **Run the query** using:
   ```bash
   python "$FM_SCRIPTS/fm_manage.py" --project-dir <path> query <solution> <command> [args]
   ```

3. **Available query commands:**
   - Script analysis: `script`, `script-raw`, `script-refs`, `script-calls`, `script-fields`, `script-layouts`, `script-cfs`, `scripts`, `deps`
   - Custom functions: `custom-functions` (alias `cfs`), `custom-function` (alias `cf`)
   - Schema: `tables`, `table`, `field`, `field-refs`, `layouts`, `layout`, `relationships`, `value-lists`
   - Search: `search`, `summary`

4. **For diagnostics** use the `diagnose` subcommand instead:
   ```bash
   python "$FM_SCRIPTS/fm_manage.py" --project-dir <path> diagnose <solution> <command>
   ```
   Commands: `hotspots`, `trace`, `slow-patterns`, `impact`, `orphans`, `health`, `duplicates`, `no-error-handling`, `dead-code`, `anti-patterns`.

5. **Interpret the output** in FileMaker-developer terms. If the user asked a question like "why is X slow?", chain multiple commands: `search` for entry points, `trace` for call trees, `slow-patterns` for anti-patterns, and synthesize.

Always run the actual commands — never fabricate script names, step counts, or analysis results.
