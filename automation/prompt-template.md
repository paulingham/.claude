/intake

## Jira Ticket: {{TICKET_KEY}}

**Summary**: {{SUMMARY}}
**Type**: {{ISSUE_TYPE}}
**Priority**: {{PRIORITY}}
**Components**: {{COMPONENTS}}
**Labels**: {{LABELS}}
**Epic**: {{EPIC_KEY}}
**Branch**: {{BRANCH_NAME}} (already created and checked out)

### Description

{{DESCRIPTION}}

### Acceptance Criteria

{{ACCEPTANCE_CRITERIA}}

---

## Automation Context

This is an automated pipeline run triggered from Jira. Important context:

1. **Branch is ready**: The branch `{{BRANCH_NAME}}` has already been created from latest `origin/main` and is checked out. Do NOT create a new branch.
2. **Full pipeline required**: Run the complete pipeline through to `/pr-creation`. The PR title MUST include `{{TICKET_KEY}}` for Jira integration.
3. **No human interaction**: This is non-interactive. If you encounter ambiguity (Ambiguity >= 2), make the most reasonable choice and document it in the PR description rather than blocking.
4. **PR description**: Include `Closes {{TICKET_KEY}}` in the PR body for Jira smart commit integration.
5. **Budget cap**: Stay within the configured budget. If the task is too large (Complexity Budget >= 13), output `VERDICT: DECOMPOSE_REQUIRED` with a breakdown of sub-tasks, and do NOT proceed with implementation.
6. **Error output**: If the pipeline cannot complete, output `VERDICT: PIPELINE_FAILED` with the reason.

### Expected Outputs

On success, your final output MUST include:
- `PR URL: https://github.com/...` (the created PR URL)
- `VERDICT: PIPELINE_COMPLETE`
- Cost summary

On failure:
- `VERDICT: PIPELINE_FAILED` or `VERDICT: DECOMPOSE_REQUIRED`
- Reason for failure
- Which phase failed and why
