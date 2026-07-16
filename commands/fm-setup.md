---
description: Index a new FileMaker DDR XML export into the current project
---

The user wants to add a new FileMaker solution to the current project. Follow these steps:

0. **Check the environment before you start indexing.** The streaming indexer in v0.3.0+ handles multi-hundred-MB DDRs in well under 500 MB of RAM, so most exports are safe to index anywhere. But if the user is on an older version (see `${CLAUDE_PLUGIN_ROOT}/.claude-plugin/plugin.json` → `version`) OR the sandbox is unusually constrained, a very large file can still thrash. Before running the indexer, size up the file and the environment:

   ```bash
   ls -la "<path/to/file.xml>"                   # bytes
   free -m 2>/dev/null || vm_stat | head         # available RAM
   ```

   If the XML file is **> 50 MB** AND available RAM is **less than 4× the file size**, don't grind through it in-sandbox. Offer the user one of these escape hatches:

   - **Cloud session.** If the file lives on their device, ask them to `gzip` it there first (DDR XML compresses 10–20×), stage the `.xml.gz` in a Cowork-connected cloud folder, and re-run `/fm-setup` from a cloud session. The larger cloud sandbox usually has enough RAM to index the file in place.
   - **Native run** (works everywhere). The plugin's `scripts/` directory is pure standard-library Python — no `pip install` needed. Copy `scripts/` into a folder the user can reach from Terminal (in Cowork: commit it to a connected folder), then hand them this paste-ready command:

     ```bash
     cd "<folder containing the XML>" \
       && python3 "<path>/scripts/fm_manage.py" index "<file>.xml" \
       && python3 "<path>/scripts/fm_manage.py" query "<name>" summary
     ```

     Once they confirm it finished, verify the resulting `solutions/` index (check `.fm_db_cache/<name>.db` exists, then run `fm_manage.py query <name> summary` yourself) and report the counts back.

   If the file is small or RAM is plentiful, skip to step 1 and proceed normally.

1. **Find the XML file.** Ask the user for the path to the DDR XML export if it wasn't provided. The file is typically UTF-16 encoded and starts with `<?xml version="1.0" encoding="UTF-16"?><FMSaveAsXML>`.

2. **Determine the current project folder.** Use the current working directory. If no `solutions/` folder exists yet, the indexer will create one. If the user is not in their intended project folder, ask before proceeding.

3. **Run the indexer** via the plugin's fm_manage.py:
   ```bash
   python ${CLAUDE_PLUGIN_ROOT}/scripts/fm_manage.py index <xml_path>
   ```
   Optionally add `--name CustomName` if the user wants a different solution name than the XML filename.

4. **Verify the index** by running a summary:
   ```bash
   python ${CLAUDE_PLUGIN_ROOT}/scripts/fm_manage.py query <name> summary
   ```

5. **Report back** with the counts: tables, fields, scripts, layouts, relationships, custom functions, and CF cross-references.

6. **Offer next steps.** Suggest running `/fm-query <name> hotspots` to see the biggest scripts, `/fm-query <name> health` for a code quality scorecard, or `/fm-review` to start an interactive code review.

Do NOT invent script names or analysis results — always run the actual commands and report the actual output.
