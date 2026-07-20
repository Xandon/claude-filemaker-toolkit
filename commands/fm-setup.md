---
description: Index a new FileMaker DDR XML export into the current project
---

The user wants to add a new FileMaker solution to the current project. Follow these steps:

0. **Check the file size before you start indexing.** The streaming indexer in v0.3.0+ keeps peak RSS bounded by the largest single catalog, so most DDRs are safe to index in-sandbox. Very large DDRs are the exception. Before running the indexer, size up the file:

   ```bash
   ls -la "<path/to/file.xml>"    # bytes
   ```

   **Hard rule — no exceptions.** If the XML file is **> 50 MB** — OR the current session is a cloud / Cowork sandbox and the file lives on the user's device — the indexer runs **on the user's machine via native Terminal `python3`.** Full stop.

   > **NEVER stage, upload, gzip-and-transfer, or otherwise move a large DDR XML into a cloud sandbox to index it. NEVER run the indexer over the device bridge. Large DDRs stay on the user's machine and are indexed by native Terminal `python3`, producing the `solutions/` index in the user's local project folder.**

   Available RAM is irrelevant to this decision. A cloud sandbox with plenty of RAM is still not allowed to index a large DDR — the file is not to be moved.

   Native-run flow (the only allowed path for large files):

   **Preferred: single-file wrapper.** The plugin ships a shell wrapper at `scripts/fm_index_wrapper.sh` that locates the plugin's `fm_manage.py` in the user's installed plugin and runs `index` + `query summary` from the current directory. **Only one file lands in the user's project folder — no Python files need to be copied.**

   1. Copy just `${CLAUDE_PLUGIN_ROOT}/scripts/fm_index_wrapper.sh` into the folder that contains the XML file (a connected Cowork folder that the user can navigate to locally). Make sure it's executable: the file ships with mode 0755 and should retain it, but if the copy strips permissions run `chmod +x fm_index_wrapper.sh`.
   2. Hand the user this paste-ready command:

      ```bash
      cd "<folder containing the XML>" \
        && ./fm_index_wrapper.sh "<file>.xml"
      ```

      Optional: append `--name <solution-name>` to override the default (file basename minus `.xml`).

   3. Wait for the user to confirm it finished. Then verify the resulting index over the connected folder (check `.fm_db_cache/<name>.db` exists, run `fm_manage.py query <name> summary` yourself against that DB) and report the counts back.

   **Fallback (only if the wrapper can't find the plugin):** if the user runs the wrapper and it errors with "Could not locate fm_manage.py", they either don't have the plugin installed or it lives in a non-standard location. Two options in that case:

   - Ask the user to install / reinstall the plugin in Cowork (Customize → Personal plugins), then retry the wrapper.
   - Or copy the plugin's full `scripts/` directory into the same connected folder and either export `FM_MANAGE_PATH=<abs path>/scripts/fm_manage.py` before running the wrapper, OR bypass the wrapper entirely with:

     ```bash
     cd "<folder containing the XML>" \
       && python3 "<path>/scripts/fm_manage.py" index "<file>.xml" \
       && python3 "<path>/scripts/fm_manage.py" query "<name>" summary
     ```

   If the file is **≤ 50 MB** AND this is not a cloud/Cowork sandbox with a device-resident file, proceed to step 1 and index in place.

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
