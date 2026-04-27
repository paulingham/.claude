---
category: decision
---

Round-1 review fixes applied (1 CRITICAL, 2 HIGH, 3 MEDIUM):

1. **Verdict strings (agents/planning-agent.md)** — `PLAN_STABLE`→`PLAN_UNCHANGED`; removed `PLAN_AGENT_ERROR`. SKILL.md remains the single source of truth for the verdict contract; agent definition now matches.

2. **Hook stdin JSON (hooks/planning-agent-edit-scope.sh)** — rewrote to read PreToolUse stdin JSON (`tool_name`, `subagent_type`, `tool_input.file_path`, `session_id`) using the peer hook pattern (see `pre-agent-allowlist.sh`, `depth-guard.sh`). Env-var sourcing was a silent no-op because the harness does not populate those vars for this hook category.

3. **Anchored regex + path normalization** — replaced unanchored `=~ pipeline-state/[^/]+-plan\.md$` with a two-part check: (a) prefix match against `realpath(worktree/pipeline-state)`, AND (b) basename matches `^[A-Za-z0-9_-]+-plan\.md$`. **Trade-off**: had to use `python3 -c 'os.path.realpath(...)'` instead of BSD `realpath` because macOS `realpath` returns empty for non-existent files, which would let `pipeline-state/../../etc/x-plan.md` slip through the prefix check (the raw path string still starts with the allowed prefix). Python normalizes `..` even on non-existent paths.

4. **Session ID sanitization** — `tr -dc 'A-Za-z0-9_-' | head -c 64` immediately after reading from JSON. Blocks directory traversal in the log path.

5. **JSON log via jq** — replaced `printf '{"...":"%s"...}' "$FILE_PATH"` with `jq -nc --arg ...` to handle quotes/newlines/control chars in user-controlled paths.

6. **1MB read cap (scratchpad_finding_parser.py)** — `path.open("rb")` + `fh.read(MAX_BYTES)` instead of unbounded `read_bytes()`.

7. **peek/commit split (scratchpad_diff.py)** — added `peek_new_findings` (no cursor mutation) and `commit_findings` (mark seen). `diff_new_findings` retained as a peek+commit convenience wrapper for back-compat. Updated `skills/continuous-planning/SKILL.md` poll loop to use the split API and only commit AFTER the plan Edit + broadcast succeed. **Trade-off**: had to extract cursor I/O into a new `scratchpad_cursor.py` module to stay under the 50-line file shape limit; this is a clean separation (cursor persistence is a distinct concern from finding diffing) so it's an improvement, not a workaround.

8. **thinking-defaults.md** — added `planning-agent` row with `effort=low` and `xhigh trigger=never`; added explanatory paragraph below the table; added planning-agent to the xhigh Leakage Boundary "NEVER applied to" list. The resolver itself was not modified — `effort=low` is declared in the agent's frontmatter; the resolver's role-effort logic only handles xhigh escalation, and the planning-agent is not subject to that.

**Verification**: 786 python tests pass (5 new for peek/commit), 11 hook tests pass (3 new for traversal/whitespace/session-sanitization), bash syntax check clean.
