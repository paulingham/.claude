#!/usr/bin/env bash
# agent-injection-capability — pure capability probe for PreToolUse:Agent
# resolver hooks (no side effects).
#
# Source this file to define agent_injection_supported. The function is PURE:
# it only returns 0 or 1. It does NOT exit, does NOT write stdout, does NOT
# log, and does NOT source harness-paths.sh. The caller decides what to do with
# the verdict. Mirrors the zero-side-effect contract of check-bypass-gate.sh.
#
# Usage (place BELOW the `SUBAGENT_TYPE=$(...)` parse, ABOVE the python `OUT=`):
#   source "${HOOK_DIR}/_lib/agent-injection-capability.sh"
#   agent_injection_supported || exit 0
#
# Contract:
#   agent_injection_supported
#     Returns 0 (supported → run the resolver) iff CLAUDE_AGENT_INJECTION_FORCE == "1"
#     Returns 1 (unsupported → skip the python) otherwise (unset, empty, "0", ...)
#
# Path A pending — flip this body to a real schema probe when Claude Code
# exposes modified_tool_input for the Agent matcher; the env escape then becomes
# a manual force-override. If hooks.jsonl Agent records lose subagent_type,
# someone moved the probe ABOVE the SUBAGENT_TYPE parse — move it back below.
#
# The indirect-expansion default ${CLAUDE_AGENT_INJECTION_FORCE:-0} mirrors the
# :-0 default + == "1" equality idiom used by check-bypass-gate.sh.
agent_injection_supported() {
  [[ "${CLAUDE_AGENT_INJECTION_FORCE:-0}" == "1" ]]
}
