#!/usr/bin/env bash
# probe-schema-flips.sh — C10 schema-flip audit one-shot probe.
#
# Drives the four Path-B advisory resolvers directly with synthetic stdin
# payloads (field-present and field-absent) so we can measure whether the
# consumer-side wiring would handle the awaited Agent-tool schema fields if
# Claude Code ever exposed them. Also counts last-30-day "would-fire"
# occurrences in the existing forensic JSONL streams under metrics/.
#
# Output: a single JSON file at
#   pipeline-state/c10-schema-flip-audit/probe-output.json
# (also printed to stdout). The four top-level keys map 1:1 to the awaited
# fields:
#   - thinking            → tool_input.thinking
#   - advisor             → tool_input.advisor
#   - allowed_tools       → tool_input.allowed_tools
#   - modified_tool_input → PreToolUse modified_tool_input
#
# Constraints honoured:
#   - Bash + jq + python3 only (matches scripts/hook-summary.sh stack).
#   - Quoted paths; CLAUDE_CONFIG_DIR resolves with $HOME/.claude default.
#   - No Agent-tool invocations — resolvers driven directly via stdin.
#   - The instinct-injector resolver writes a real JSONL line; we use a
#     throwaway CLAUDE_SESSION_ID and clean its metrics dir at the end.
#   - Idempotent and side-effect-free against the rest of the harness.
set -uo pipefail

CLAUDE_DIR="${CLAUDE_CONFIG_DIR:-$HOME/.claude}"
LIB_DIR="${CLAUDE_DIR}/hooks/_lib"
METRICS_DIR="${CLAUDE_DIR}/metrics"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
OUT_DIR="${REPO_ROOT}/pipeline-state/c10-schema-flip-audit"
OUT_FILE="${OUT_DIR}/probe-output.json"
PROBE_SESSION="probe-$$"
PROBE_METRICS_DIR="${METRICS_DIR}/${PROBE_SESSION}"

mkdir -p "${OUT_DIR}"

cleanup() {
  rm -rf "${PROBE_METRICS_DIR}" 2>/dev/null || true
}
trap cleanup EXIT

# ---------------------------------------------------------------------------
# Resolver drivers — pipe a JSON payload to a resolver, capture stdout lines.
# ---------------------------------------------------------------------------

drive_thinking() {
  # Prints two lines: decision\n{resolved JSON}
  local payload="$1"
  printf '%s' "${payload}" | python3 "${LIB_DIR}/resolve-thinking.py"
}

drive_advisor() {
  local payload="$1"
  printf '%s' "${payload}" | python3 "${LIB_DIR}/resolve-advisor.py"
}

drive_tool_allowlist() {
  # Prints three lines: decision\nresolved\nfrontmatter
  local payload="$1"
  printf '%s' "${payload}" | python3 "${LIB_DIR}/resolve-tool-allowlist.py"
}

drive_instincts() {
  # Side-effecting: writes a JSONL line under the probe session.
  local payload="$1"
  printf '%s' "${payload}" \
    | CLAUDE_SESSION_ID="${PROBE_SESSION}" \
      python3 "${LIB_DIR}/resolve-instincts.py"
}

# ---------------------------------------------------------------------------
# 30-day would-fire counters. Filenames follow the rules in the task spec.
# ---------------------------------------------------------------------------

cutoff_30d() {
  python3 -c '
import datetime
cutoff = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=30)
print(cutoff.strftime("%Y-%m-%dT%H:%M:%SZ"))
'
}

count_records() {
  # Args: <jsonl-basename> <jq-filter-expression>
  # The jq filter receives each record and must return true for matches.
  # We embed a 30-day timestamp cutoff (UTC) to filter records by `timestamp`.
  local basename="$1"
  local filter="$2"
  local cutoff
  cutoff="$(cutoff_30d)"

  local total=0
  while IFS= read -r path; do
    [ -z "${path}" ] && continue
    local n
    # shellcheck disable=SC2016
    n="$(jq -r --arg cutoff "${cutoff}" \
      "select(.timestamp >= \$cutoff) | select(${filter}) | 1" \
      "${path}" 2>/dev/null | wc -l | tr -d ' ' )"
    [ -z "${n}" ] && n=0
    total=$(( total + n ))
  done < <(find "${METRICS_DIR}" -maxdepth 2 -type f -name "${basename}" 2>/dev/null)
  printf '%d' "${total}"
}

count_instinct_drift() {
  # Returns "<logged_with_kept> <orchestrator_injected> <drift>" on stdout.
  local cutoff
  cutoff="$(cutoff_30d)"

  local logged=0 injected=0
  while IFS= read -r path; do
    [ -z "${path}" ] && continue
    local lk inj
    # shellcheck disable=SC2016
    lk="$(jq -r --arg cutoff "${cutoff}" \
      'select(.timestamp >= $cutoff)
       | select(.source == "logged" and (.resolved.count_kept // 0) > 0)
       | 1' \
      "${path}" 2>/dev/null | wc -l | tr -d ' ' )"
    # shellcheck disable=SC2016
    inj="$(jq -r --arg cutoff "${cutoff}" \
      'select(.timestamp >= $cutoff)
       | select(.source == "orchestrator-injected")
       | 1' \
      "${path}" 2>/dev/null | wc -l | tr -d ' ' )"
    [ -z "${lk}" ] && lk=0
    [ -z "${inj}" ] && inj=0
    logged=$(( logged + lk ))
    injected=$(( injected + inj ))
  done < <(find "${METRICS_DIR}" -maxdepth 2 -type f -name "instinct-injections.jsonl" 2>/dev/null)

  local drift=$(( logged - injected ))
  [ "${drift}" -lt 0 ] && drift=0
  printf '%d %d %d' "${logged}" "${injected}" "${drift}"
}

# ---------------------------------------------------------------------------
# 1. THINKING — tool_input.thinking present vs absent.
# ---------------------------------------------------------------------------

# Field absent: resolver should report decision=LOG, source ∈ {role, default}.
THINKING_ABSENT_PAYLOAD='{
  "tool_name": "Agent",
  "tool_input": {
    "subagent_type": "software-engineer",
    "description": "schema-flip probe (absent)",
    "prompt": "probe"
  }
}'

# Field present: resolver should report decision=SKIP, source=explicit.
THINKING_PRESENT_PAYLOAD='{
  "tool_name": "Agent",
  "tool_input": {
    "subagent_type": "software-engineer",
    "description": "schema-flip probe (present)",
    "prompt": "probe",
    "thinking": {"effort": "xhigh", "display": "text"}
  }
}'

THINKING_ABSENT_OUT="$(drive_thinking "${THINKING_ABSENT_PAYLOAD}")"
THINKING_ABSENT_DECISION="$(printf '%s' "${THINKING_ABSENT_OUT}" | sed -n '1p')"
THINKING_ABSENT_RESOLVED="$(printf '%s' "${THINKING_ABSENT_OUT}" | sed -n '2p')"

THINKING_PRESENT_OUT="$(drive_thinking "${THINKING_PRESENT_PAYLOAD}")"
THINKING_PRESENT_DECISION="$(printf '%s' "${THINKING_PRESENT_OUT}" | sed -n '1p')"
THINKING_PRESENT_RESOLVED="$(printf '%s' "${THINKING_PRESENT_OUT}" | sed -n '2p')"

THINKING_30D_COUNT="$(count_records "hook-injections.jsonl" \
  '.resolved.source == "explicit"')"

# ---------------------------------------------------------------------------
# 2. ADVISOR — tool_input.advisor present vs absent.
# Note: advisor_resolver does not consume tool_input.advisor today; the
# resolver is fed by frontmatter only. We probe both shapes anyway so the
# audit captures the consumer-side decision both ways. Frontmatter-side
# pairing is exercised against `code-reviewer` (declares advisor: opus).
# ---------------------------------------------------------------------------

ADVISOR_ABSENT_PAYLOAD='{
  "tool_name": "Agent",
  "tool_input": {
    "subagent_type": "code-reviewer",
    "description": "schema-flip probe (absent)",
    "prompt": "probe"
  }
}'

ADVISOR_PRESENT_PAYLOAD='{
  "tool_name": "Agent",
  "tool_input": {
    "subagent_type": "code-reviewer",
    "description": "schema-flip probe (present)",
    "prompt": "probe",
    "advisor": "claude-opus-4-5-20251101"
  }
}'

ADVISOR_ABSENT_OUT="$(drive_advisor "${ADVISOR_ABSENT_PAYLOAD}")"
ADVISOR_ABSENT_DECISION="$(printf '%s' "${ADVISOR_ABSENT_OUT}" | sed -n '1p')"
ADVISOR_ABSENT_RESOLVED="$(printf '%s' "${ADVISOR_ABSENT_OUT}" | sed -n '2p')"

ADVISOR_PRESENT_OUT="$(drive_advisor "${ADVISOR_PRESENT_PAYLOAD}")"
ADVISOR_PRESENT_DECISION="$(printf '%s' "${ADVISOR_PRESENT_OUT}" | sed -n '1p')"
ADVISOR_PRESENT_RESOLVED="$(printf '%s' "${ADVISOR_PRESENT_OUT}" | sed -n '2p')"

ADVISOR_30D_COUNT="$(count_records "advisor-dispatch.jsonl" \
  '.resolved.source == "explicit"')"

# ---------------------------------------------------------------------------
# 3. ALLOWED_TOOLS — tool_input.allowed_tools present vs absent.
# Probes the would_block branch by requesting a tool NOT in the agent's
# frontmatter `tools:` list. infrastructure-engineer's list does not
# include ToolThatDoesNotExist.
# ---------------------------------------------------------------------------

ALLOWED_TOOLS_ABSENT_PAYLOAD='{
  "tool_name": "Agent",
  "tool_input": {
    "subagent_type": "infrastructure-engineer",
    "description": "schema-flip probe (absent)",
    "prompt": "probe"
  }
}'

ALLOWED_TOOLS_PRESENT_PAYLOAD='{
  "tool_name": "Agent",
  "tool_input": {
    "subagent_type": "infrastructure-engineer",
    "description": "schema-flip probe (present)",
    "prompt": "probe",
    "allowed_tools": ["Read", "ToolThatDoesNotExist"]
  }
}'

ALLOWED_TOOLS_ABSENT_OUT="$(drive_tool_allowlist "${ALLOWED_TOOLS_ABSENT_PAYLOAD}")"
ALLOWED_TOOLS_ABSENT_DECISION="$(printf '%s' "${ALLOWED_TOOLS_ABSENT_OUT}" | sed -n '1p')"
ALLOWED_TOOLS_ABSENT_RESOLVED="$(printf '%s' "${ALLOWED_TOOLS_ABSENT_OUT}" | sed -n '2p')"

ALLOWED_TOOLS_PRESENT_OUT="$(drive_tool_allowlist "${ALLOWED_TOOLS_PRESENT_PAYLOAD}")"
ALLOWED_TOOLS_PRESENT_DECISION="$(printf '%s' "${ALLOWED_TOOLS_PRESENT_OUT}" | sed -n '1p')"
ALLOWED_TOOLS_PRESENT_RESOLVED="$(printf '%s' "${ALLOWED_TOOLS_PRESENT_OUT}" | sed -n '2p')"

ALLOWED_TOOLS_30D_COUNT="$(count_records "tool-allowlist.jsonl" \
  '.action == "would_block"')"

# ---------------------------------------------------------------------------
# 4. MODIFIED_TOOL_INPUT — instinct-injector resolver. The resolver writes
# a JSONL line under CLAUDE_SESSION_ID; we use the throwaway probe session
# so we never pollute another session's metrics. We still capture what the
# resolver *would* inject by reading the line back.
# ---------------------------------------------------------------------------

INSTINCT_PAYLOAD='{
  "tool_name": "Agent",
  "tool_input": {
    "subagent_type": "infrastructure-engineer",
    "description": "schema-flip probe (instinct)",
    "prompt": "probe"
  }
}'

drive_instincts "${INSTINCT_PAYLOAD}" >/dev/null 2>&1 || true

INSTINCT_PROBE_FILE="${PROBE_METRICS_DIR}/instinct-injections.jsonl"
if [ -f "${INSTINCT_PROBE_FILE}" ]; then
  INSTINCT_RESOLVED_LINE="$(tail -n 1 "${INSTINCT_PROBE_FILE}")"
else
  INSTINCT_RESOLVED_LINE='{}'
fi

read -r INSTINCT_LOGGED INSTINCT_INJECTED INSTINCT_DRIFT <<<"$(count_instinct_drift)"

# ---------------------------------------------------------------------------
# Compose JSON output.
# ---------------------------------------------------------------------------

# Each `resolved_*` capture is already a JSON line. We feed them into jq
# unchanged so the output stays valid JSON regardless of resolver internals.
jq -n \
  --arg session "${PROBE_SESSION}" \
  --argjson thinking_present_resolved   "${THINKING_PRESENT_RESOLVED:-null}" \
  --argjson thinking_absent_resolved    "${THINKING_ABSENT_RESOLVED:-null}" \
  --arg     thinking_present_decision   "${THINKING_PRESENT_DECISION}" \
  --arg     thinking_absent_decision    "${THINKING_ABSENT_DECISION}" \
  --argjson thinking_30d_count          "${THINKING_30D_COUNT:-0}" \
  --argjson advisor_present_resolved    "${ADVISOR_PRESENT_RESOLVED:-null}" \
  --argjson advisor_absent_resolved     "${ADVISOR_ABSENT_RESOLVED:-null}" \
  --arg     advisor_present_decision    "${ADVISOR_PRESENT_DECISION}" \
  --arg     advisor_absent_decision     "${ADVISOR_ABSENT_DECISION}" \
  --argjson advisor_30d_count           "${ADVISOR_30D_COUNT:-0}" \
  --argjson allowed_present_resolved    "${ALLOWED_TOOLS_PRESENT_RESOLVED:-null}" \
  --argjson allowed_absent_resolved     "${ALLOWED_TOOLS_ABSENT_RESOLVED:-null}" \
  --arg     allowed_present_decision    "${ALLOWED_TOOLS_PRESENT_DECISION}" \
  --arg     allowed_absent_decision     "${ALLOWED_TOOLS_ABSENT_DECISION}" \
  --argjson allowed_30d_count           "${ALLOWED_TOOLS_30D_COUNT:-0}" \
  --argjson instinct_resolved           "${INSTINCT_RESOLVED_LINE:-null}" \
  --argjson instinct_logged_with_kept   "${INSTINCT_LOGGED:-0}" \
  --argjson instinct_orchestrator_injected "${INSTINCT_INJECTED:-0}" \
  --argjson instinct_drift              "${INSTINCT_DRIFT:-0}" \
  '{
    probe_session: $session,
    generated_utc: (now | strftime("%Y-%m-%dT%H:%M:%SZ")),
    thinking: {
      awaited_field: "tool_input.thinking",
      probe_present: { decision: $thinking_present_decision, resolved: $thinking_present_resolved },
      probe_absent:  { decision: $thinking_absent_decision,  resolved: $thinking_absent_resolved  },
      last_30d_would_fire_count: $thinking_30d_count,
      count_definition: "records in hook-injections.jsonl with .resolved.source == \"explicit\""
    },
    advisor: {
      awaited_field: "tool_input.advisor",
      probe_present: { decision: $advisor_present_decision, resolved: $advisor_present_resolved },
      probe_absent:  { decision: $advisor_absent_decision,  resolved: $advisor_absent_resolved  },
      last_30d_would_fire_count: $advisor_30d_count,
      count_definition: "records in advisor-dispatch.jsonl with .resolved.source == \"explicit\""
    },
    allowed_tools: {
      awaited_field: "tool_input.allowed_tools",
      probe_present: { decision: $allowed_present_decision, resolved: $allowed_present_resolved },
      probe_absent:  { decision: $allowed_absent_decision,  resolved: $allowed_absent_resolved  },
      last_30d_would_fire_count: $allowed_30d_count,
      count_definition: "records in tool-allowlist.jsonl with .action == \"would_block\""
    },
    modified_tool_input: {
      awaited_field: "PreToolUse modified_tool_input",
      probe_present: { decision: "LOG", resolved: $instinct_resolved },
      probe_absent:  { decision: "LOG", resolved: null,
                       note: "instinct-injector always logs; no field-absent branch to probe" },
      last_30d_logged_with_kept_count: $instinct_logged_with_kept,
      last_30d_orchestrator_injected_count: $instinct_orchestrator_injected,
      last_30d_drift: $instinct_drift,
      count_definition: "drift = (logged with resolved.count_kept > 0) - (orchestrator-injected) in instinct-injections.jsonl"
    }
  }' > "${OUT_FILE}"

cat "${OUT_FILE}"
