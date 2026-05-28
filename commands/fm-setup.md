---
description: Index a new FileMaker DDR XML export into the current project
---

The user wants to add a new FileMaker solution to the current project. Follow these steps:

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
