---
category: discovery
---
SubagentStop payload field path confirmed: `.subagent_type` is TOP-LEVEL (no `.tool_input` wrapper), matching `subagent-stop-trajectory.sh`. Token usage assumed at `.usage.input_tokens` / `.usage.output_tokens` / `.usage.cache_read_input_tokens` (top level, mirroring the asymmetry). Field-path verification call-out preserved as a header comment in `hooks/_lib/cost-helpers.sh` for future reviewers.

---
category: pattern
---
Cost-feed hook decomposition: `hooks/cost-feed.sh` (41 LOC, orchestration only) + `hooks/_lib/cost-helpers.sh` (40 LOC, five 2-5 line helpers: pipeline-id resolver, session-id sanitizer, JSON field resolver with env fallback, token coercer, jq-float cost compute). Follows the `_lib/` extraction pattern already established by `runtime-guard-key.sh` and `depth-guard-log.sh`. Every function body ≤5 lines, both files ≤50 lines.

---
category: warning
---
Fail-open is load-bearing. Every error path exits 0 — hook never crashes a pipeline. Six explicit fail-open guards: jq parse, empty stdin, all-zero tokens, empty cost compute output, mkdir failure, jq-write failure. Validated by T13 (malformed JSON) and T14 (empty stdin) tests. Future edits MUST preserve `set -uo pipefail` (no `-e`) and the trailing `|| true` / `|| exit 0` guards.

---
category: decision
---
Chose `ls -t | head -1` for newest-mtime pipeline-id resolution over `find -printf %T@`, with a `# shellcheck disable=SC2012` directive. Reason: `find -printf` is GNU-only (not portable to macOS BSD `find`), the prompt explicitly specifies the `ls -t` form, and pipeline-state filenames are controlled (no spaces/newlines). Trade-off accepted: shellcheck info-level note silenced via inline directive.
