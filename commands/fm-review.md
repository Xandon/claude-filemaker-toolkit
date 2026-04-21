---
description: Start an interactive FileMaker script code review
---

The user wants to perform a code review on one or more FileMaker scripts and generate an interactive HTML report.

## Workflow

0. **Locate the plugin scripts.** In the Cowork sandbox, `$CLAUDE_PLUGIN_ROOT` may not be set. Discover the path first:
   ```bash
   FM_SCRIPTS=$(dirname "$(find /sessions -path '*/scripts/fm_manage.py' -print -quit 2>/dev/null)")
   ```
   Use `$FM_SCRIPTS/fm_manage.py` for all commands below. If the user's project folder is not the cwd, pass `--project-dir <path>`.

1. **Identify the target scripts.** Ask the user which script(s) to review if not provided. Use `fm_manage.py query <solution> scripts <pattern>` to search if needed. Resolve names to script IDs.

2. **Read the scripts** with human-readable output:
   ```bash
   python "$FM_SCRIPTS/fm_manage.py" --project-dir <path> query <solution> script "<name>"
   ```

3. **Gather context:**
   - `script-refs <name>` — who calls this?
   - `script-calls <name>` — what does this call?
   - `script-fields <name>` — what data does it touch?
   - `script-cfs <name>` — which custom functions does it use (framework patterns)?

4. **Analyze the logic.** Look for:
   - Missing error handling (Set Error Capture [On], Exit Loop If [ Error ])
   - Record lock hazards (Set Field inside loops without error checks)
   - Loops without proper Exit Loop If conditions
   - Found set assumptions (Perform Find without checking Get(foundCount))
   - Global variable conflicts
   - Disabled steps (dead code)
   - Layout/Find/Commit patterns inside loops (performance)

5. **Create a review definition JSON** at `solutions/<solution>/reviews/<name>.json`. The JSON must follow this schema:
   ```json
   {
     "meta": {
       "review_name": "Descriptive review title",
       "solution": "SolutionName",
       "created": "2026-04-10",
       "context": "Brief description of why this review was done"
     },
     "script_ids": [2937, 2938],
     "findings": [
       {
         "id": "F1",
         "severity": "critical",
         "title": "Clear title of the issue",
         "script_ids": [2937],
         "step_indices": [15, 16, 17],
         "description": "What's wrong and why it matters",
         "best_practice": "What should be done instead",
         "fix_description": "Specific steps to fix it",
         "after_steps": [
           "Set Error Capture [ On ]",
           "Perform Find []",
           "If [ Get(LastError) ≠ 0 ]",
           "  Show Custom Dialog [ \"Error\" ; \"Find failed\" ]",
           "End If"
         ]
       }
     ]
   }
   ```

   > **⚠ REQUIRED for the "Copy Fix XML" button to render:** every finding MUST
   > include exactly one of `after_steps`, `fix_step_indices`, or `fix_xml`
   > (at the finding top-level, or nested under `fix.<script_id>`). If none
   > is present, the paste-to-FileMaker button is silently omitted and the
   > user has no way to apply the fix via MBS. **`after_steps` is the
   > preferred form** — it reads naturally in the HTML diff and the generator
   > auto-builds the clipboard XML from it. Do NOT hand-author `before_human`
   > or `after_human` directly; those are derived fields.

   **Key fields for code snippets in the HTML output:**
   - `step_indices` — which steps are affected (highlighted in the left panel)
   - `after_steps` — recommended fix steps as human-readable FileMaker notation (see format below) — **REQUIRED unless you supply `fix_step_indices` or `fix_xml`**
   - `fix_step_indices` — alternative to `after_steps`: pick/reorder existing steps from the script by index (generator copies their raw XML)
   - `fix_xml` — alternative to `after_steps`: pre-authored clipboard `fmxmlsnippet` XML used as-is
   - `fix_description` — plain English explanation of the fix
   - `best_practice` — the general principle behind the recommendation

   **CRITICAL — `after_steps` format for "Copy Fix XML" button:**
   The `after_steps` array must use standard FileMaker script step notation so the generator
   can auto-convert them to pasteable `fmxmlsnippet` clipboard XML. Use these exact patterns:

   ```json
   "after_steps": [
     "Set Error Capture [ On ]",
     "Perform Find []",
     "If [ Get(LastError) ≠ 0 ]",
     "  Show Custom Dialog [ \"No Records\" ; \"The find returned no results.\" ]",
     "  Exit Script []",
     "End If",
     "Set Variable [ $count ; Value: Get(FoundCount) ]",
     "Go to Layout [ \"Detail\" ]",
     "Go to Record/Request/Page [ First ]",
     "Loop",
     "  Exit Loop If [ Get(FoundCount) = 0 ]",
     "  # Process each record",
     "  Commit Records/Requests",
     "  Go to Record/Request/Page [ Next ]",
     "End Loop",
     "Set Error Capture [ Off ]"
   ]
   ```

   Supported step types: Set Error Capture, Allow User Abort, Set Variable, Set Field,
   If/Else If/Else/End If, Loop/End Loop, Exit Loop If, Go to Layout, Perform Script,
   Perform Find, Enter Find Mode, New Record/Request, Commit Records/Requests,
   Show All Records, Freeze Window, Refresh Window, Exit Script,
   Go to Record/Request/Page, Show Custom Dialog, Delete Record/Request,
   Go to Object, Open URL, and comments (lines starting with #).

   Leading whitespace (indentation) is stripped before parsing; you may indent for readability.

   The generator automatically:
   - Reads the actual script steps for `step_indices` and shows them as "Before" code
   - Displays `after_steps` as "After" code (before/after diff view)
   - **Parses `after_steps` into proper `fmxmlsnippet` clipboard XML** for the "Copy Fix XML" button
   - The copied XML can be pasted directly into FileMaker Script Workspace via MBS plugin

   Findings should be classified as `critical` (data corruption or user-visible bug), `high` (reliability risk), or `medium` (code quality).

6. **Generate the HTML report:**
   ```bash
   python "$FM_SCRIPTS/fm_manage.py" --project-dir <path> review <solution> <review-name>.json
   ```

7. **Present the result.** Point the user at the generated HTML file in `solutions/<solution>/output/` with a computer:// link, and summarize the findings count by severity.

## Best Practices for This Review Type

- Always read the actual script output before writing findings — never fabricate steps or step indices.
- If the solution uses a custom function framework (Error, DeclareVariables, ExitScript, etc.), acknowledge it in the review context — framework-driven scripts handle errors through CFs, not always through direct Get(LastError) checks.
- Prefer showing the exact step numbers being critiqued so the user can cross-reference with FileMaker's Script Workspace.
- Use severity thoughtfully: critical = data corruption or user-visible bug, high = reliability risk, medium = code quality or cosmetic.
