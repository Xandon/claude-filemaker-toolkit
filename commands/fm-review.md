---
description: Start an interactive FileMaker script code review
---

The user wants to perform a code review on one or more FileMaker scripts and generate an interactive HTML report.

## Workflow

1. **Identify the target scripts.** Ask the user which script(s) to review if not provided. Use `fm_manage.py query <solution> scripts <pattern>` to search if needed. Resolve names to script IDs.

2. **Read the scripts** with human-readable output:
   ```bash
   python ${CLAUDE_PLUGIN_ROOT}/scripts/fm_manage.py query <solution> script "<name>"
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

5. **Create a review definition JSON** at `solutions/<solution>/reviews/<name>.json` with findings classified as `critical`, `high`, or `medium`. Each finding should have:
   - A clear title
   - The affected script_ids and step indices
   - A description of what's wrong
   - A best_practice explanation
   - A fix_description
   - Before/after code (`before_human`, `after_human`) for the diff view
   - **Paste-ready fix XML — REQUIRED whenever `after_human` is present.**
     Without it the user gets a text-only Copy button and has to hand-translate
     the fix back into FileMaker. Pick the right form for the fix:

     **Best default: `after_steps`** — an array of step dicts the generator
     passes to `fm_xml_gen.generate_step_xml`:
     ```json
     "after_steps": [
       { "type": "set_error_capture", "on": "True" },
       { "type": "if",            "condition": "Get(foundCount) = 0" },
       { "type": "exit_script" },
       { "type": "end_if" }
     ]
     ```

     If the fix is "keep these existing steps in this order", use
     `fix_step_indices: [12, 13, 14]` — the generator extracts those steps
     verbatim from the original script.

     For exotic step types the template library can't express, hand-author
     `fix_xml`: a full `<fmxmlsnippet type="FMObjectList">…</fmxmlsnippet>`
     string.

     **If the finding is purely informational** (rename suggestion, code-smell
     flag with no specific replacement), omit the `fix` block entirely — the
     card correctly gets no Copy button.

6. **Generate the HTML report:**
   ```bash
   python ${CLAUDE_PLUGIN_ROOT}/scripts/fm_manage.py review <solution> <review-name>.json
   ```

   **Watch the generator output for ⚠️  WARNING lines** listing findings whose
   fix lacks paste-ready XML. If any appear, fix the review JSON (add
   `after_steps`) and regenerate before presenting to the user.

7. **Present the result.** Point the user at the generated HTML file in `solutions/<solution>/output/` with a computer:// link, and summarize the findings count by severity. If any fixes still ship as text-only, surface that to the user honestly.

## Best Practices for This Review Type

- Always read the actual script output before writing findings — never fabricate steps or step indices.
- If the solution uses a custom function framework (Error, DeclareVariables, ExitScript, etc.), acknowledge it in the review context — framework-driven scripts handle errors through CFs, not always through direct Get(LastError) checks.
- Prefer showing the exact step numbers being critiqued so the user can cross-reference with FileMaker's Script Workspace.
- Use severity thoughtfully: critical = data corruption or user-visible bug, high = reliability risk, medium = code quality or cosmetic.
- **Never ship a fix card with only `after_human` set.** If you have time to write the AFTER text, you have time to write `after_steps`. The Copy button is what makes the review actionable.
