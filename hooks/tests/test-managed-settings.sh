#!/usr/bin/env bash
# test-managed-settings.sh — ACs A1-A9 for production managed-settings.json (Slice 4)
# Run from the repo root: bash hooks/tests/test-managed-settings.sh
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
FILE="$REPO_ROOT/managed-settings.json"

PASS=0
FAIL=0
ERRORS=""

pass() { PASS=$((PASS + 1)); echo "  PASS: $1"; }
fail() { FAIL=$((FAIL + 1)); ERRORS="$ERRORS\n  FAIL: $1"; echo "  FAIL: $1"; }

echo "=== test-managed-settings.sh ==="
echo "File: $FILE"
echo ""

# A1 — valid JSON
echo "A1: valid JSON"
if python3 -m json.tool "$FILE" > /dev/null 2>&1; then
  pass "A1 valid JSON"
else
  fail "A1 invalid JSON"
fi

# A2 — plugin delivery keys present
echo "A2: plugin delivery keys"
if python3 - "$FILE" <<'PYEOF'
import json, sys
d = json.load(open(sys.argv[1]))
assert "extraKnownMarketplaces" in d, "missing extraKnownMarketplaces"
assert "enabledPlugins" in d, "missing enabledPlugins"
assert "strictKnownMarketplaces" in d, "missing strictKnownMarketplaces"
assert "paulingham" in d["extraKnownMarketplaces"], "extraKnownMarketplaces missing paulingham"
assert "harness@paulingham" in d["enabledPlugins"], "enabledPlugins missing harness@paulingham"
assert d["enabledPlugins"]["harness@paulingham"] is True, "harness@paulingham not true"
assert any(e.get("source") == "github" and e.get("repo") == "paulingham/.claude"
           for e in d["strictKnownMarketplaces"]), "strictKnownMarketplaces missing github entry"
assert any(e.get("source") == "hostPattern" and e.get("hostPattern") == r"^github\.com$"
           for e in d["strictKnownMarketplaces"]), "strictKnownMarketplaces missing hostPattern entry"
PYEOF
then
  pass "A2 plugin delivery keys present"
else
  fail "A2 plugin delivery keys missing or malformed"
fi

# A3 — env has exactly the 11 required keys, no CLAUDE_PIPELINE_TASK_ID, no _doc_*
echo "A3: env keys"
if python3 - "$FILE" <<'PYEOF'
import json, sys
d = json.load(open(sys.argv[1]))
env = d.get("env", {})
required = {
    "CLAUDE_CODE_PLUGIN_KEEP_MARKETPLACE_ON_FAILURE",
    "CLAUDE_CODE_PLUGIN_GIT_TIMEOUT_MS",
    "CLAUDE_HOOK_PROFILE",
    "ENABLE_TOOL_SEARCH",
    "CLAUDE_CODE_SUBAGENT_MODEL",
    "CLAUDE_PIPELINE_MODE",
    "CLAUDE_ENABLE_TRACE",
    "CLAUDE_SUBAGENT_MAX_DEPTH",
    "CLAUDE_SUBAGENT_MAX_RUNTIME",
    "CLAUDE_TEAMMATE_MAX_RUNTIME",
    "CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS",
}
missing = required - set(env.keys())
assert not missing, f"env missing keys: {missing}"
assert "CLAUDE_PIPELINE_TASK_ID" not in env, "env must NOT contain CLAUDE_PIPELINE_TASK_ID"
doc_keys = [k for k in env if k.startswith("_doc_")]
assert not doc_keys, f"env must NOT contain _doc_* keys: {doc_keys}"
PYEOF
then
  pass "A3 env has 11 required keys, no CLAUDE_PIPELINE_TASK_ID, no _doc_*"
else
  fail "A3 env keys check failed"
fi

# A4 — permissions.deny has the 16 rules; NO defaultMode; NO disableBypassPermissionsMode; NO allow
echo "A4: permissions overridable posture"
if python3 - "$FILE" <<'PYEOF'
import json, sys
d = json.load(open(sys.argv[1]))
perms = d.get("permissions", {})
deny = perms.get("deny", [])
expected_deny = [
    "Bash(rm -rf /*)",
    "Bash(rm -rf ~*)",
    "Bash(rm -rf /Users*)",
    "Bash(rm -rf $HOME*)",
    "Bash(rm -rf /tmp*)",
    "Bash(dd if=*)",
    "Bash(mkfs*)",
    "Bash(> /dev/sda*)",
    "Bash(chmod -R 777 /*)",
    "Bash(git push --force origin main)",
    "Bash(git push --force origin master)",
    "Bash(git push -f origin main)",
    "Bash(git push -f origin master)",
    "Bash(git reset --hard*)",
    "Bash(git branch -D main)",
    "Bash(git branch -D master)",
]
assert len(deny) == 16, f"expected 16 deny rules, got {len(deny)}: {deny}"
for rule in expected_deny:
    assert rule in deny, f"deny missing rule: {rule}"
assert "defaultMode" not in d, "top-level defaultMode locks mode (breaks autonomous bypass)"
assert "defaultMode" not in perms, "permissions must NOT contain defaultMode (breaks overridable posture)"
assert "disableBypassPermissionsMode" not in perms, "permissions must NOT contain disableBypassPermissionsMode"
assert "allow" not in perms, "permissions must NOT contain allow list"
PYEOF
then
  pass "A4 permissions.deny has 16 rules; no defaultMode; no disableBypassPermissionsMode; no allow"
else
  fail "A4 permissions posture check failed"
fi

# A5 — claudeMd non-empty, contains "Iron Laws" and "$CLAUDE_PLUGIN_ROOT"
echo "A5: claudeMd content"
if python3 - "$FILE" <<'PYEOF'
import json, sys
d = json.load(open(sys.argv[1]))
cm = d.get("claudeMd", "")
assert cm, "claudeMd must be non-empty"
assert "Iron Laws" in cm, "claudeMd must contain 'Iron Laws'"
assert "$CLAUDE_PLUGIN_ROOT" in cm, "claudeMd must contain '$CLAUDE_PLUGIN_ROOT'"
PYEOF
then
  pass "A5 claudeMd non-empty, contains Iron Laws and \$CLAUDE_PLUGIN_ROOT"
else
  fail "A5 claudeMd content check failed"
fi

# A6 — SessionStart + PreToolUse inline commands sh -n clean
echo "A6: hook commands sh -n clean"
A6_OK=true
TMPDIR_SH="${TMPDIR:-/tmp}"

# Extract SessionStart command
SS_CMD=$(python3 - "$FILE" <<'PYEOF'
import json, sys
d = json.load(open(sys.argv[1]))
ss = d["hooks"]["SessionStart"]
cmd = ss[0]["hooks"][0]["command"]
print(cmd)
PYEOF
)
if [ -z "$SS_CMD" ]; then
  fail "A6 SessionStart command not extractable"
  A6_OK=false
else
  SS_FILE="$TMPDIR_SH/test-ms-ss-$$.sh"
  printf '%s\n' "$SS_CMD" > "$SS_FILE"
  if sh -n "$SS_FILE" 2>/dev/null; then
    pass "A6 SessionStart command sh -n clean"
  else
    fail "A6 SessionStart command sh -n FAILED"
    A6_OK=false
  fi
  rm -f "$SS_FILE"
fi

# Extract PreToolUse command
PTU_CMD=$(python3 - "$FILE" <<'PYEOF'
import json, sys
d = json.load(open(sys.argv[1]))
ptu = d["hooks"]["PreToolUse"]
cmd = ptu[0]["hooks"][0]["command"]
print(cmd)
PYEOF
)
if [ -z "$PTU_CMD" ]; then
  fail "A6 PreToolUse command not extractable"
  A6_OK=false
else
  PTU_FILE="$TMPDIR_SH/test-ms-ptu-$$.sh"
  printf '%s\n' "$PTU_CMD" > "$PTU_FILE"
  if sh -n "$PTU_FILE" 2>/dev/null; then
    pass "A6 PreToolUse command sh -n clean"
  else
    fail "A6 PreToolUse command sh -n FAILED"
    A6_OK=false
  fi
  rm -f "$PTU_FILE"
fi

# A7 — NO sandbox key
echo "A7: no sandbox key"
if python3 - "$FILE" <<'PYEOF'
import json, sys
d = json.load(open(sys.argv[1]))
assert "sandbox" not in d, f"managed-settings.json must NOT contain 'sandbox' key (found: {d['sandbox']})"
PYEOF
then
  pass "A7 no sandbox key"
else
  fail "A7 sandbox key present (must be excluded)"
fi

# A8 — no canary remnants
echo "A8: no canary remnants"
if ! grep -q "CLAUDE_MANAGED_SETTINGS_CANARY\|managed-test-canary" "$FILE"; then
  pass "A8 no canary remnants"
else
  fail "A8 canary remnants found (CLAUDE_MANAGED_SETTINGS_CANARY or managed-test-canary)"
fi

# A9 — settings.json byte-identical to main
echo "A9: settings.json byte-identical to main"
cd "$REPO_ROOT"
if git diff --exit-code main..HEAD -- settings.json > /dev/null 2>&1; then
  pass "A9 settings.json byte-identical to main"
else
  fail "A9 settings.json differs from main"
fi

# A10 — SessionStart command contains bootstrap imperatives (not just sh -n clean)
echo "A10: SessionStart command contains bootstrap imperatives"
if python3 - "$FILE" <<'PYEOF'
import json, sys
d = json.load(open(sys.argv[1]))
cmd = d["hooks"]["SessionStart"][0]["hooks"][0]["command"]
assert "marketplace add" in cmd, \
    "SessionStart command must contain 'marketplace add' (bootstrap: claude plugin marketplace add paulingham/.claude)"
assert "plugin install" in cmd, \
    "SessionStart command must contain 'plugin install' (bootstrap: claude plugin install harness@paulingham)"
PYEOF
then
  pass "A10 SessionStart contains 'marketplace add' and 'plugin install'"
else
  fail "A10 SessionStart bootstrap imperatives missing"
fi

# A11 — PreToolUse command emits permissionDecision:deny JSON (not just syntax-clean)
echo "A11: PreToolUse command emits permissionDecision:deny"
if python3 - "$FILE" <<'PYEOF'
import json, sys
d = json.load(open(sys.argv[1]))
cmd = d["hooks"]["PreToolUse"][0]["hooks"][0]["command"]
assert "permissionDecision" in cmd, \
    "PreToolUse command must contain 'permissionDecision' (deny-form output JSON)"
assert '"deny"' in cmd or "'deny'" in cmd or "deny" in cmd, \
    "PreToolUse command must contain deny decision"
assert "hookSpecificOutput" in cmd, \
    "PreToolUse command must emit hookSpecificOutput JSON (deny gate output format)"
PYEOF
then
  pass "A11 PreToolUse emits permissionDecision:deny hookSpecificOutput"
else
  fail "A11 PreToolUse deny-form output missing"
fi

# A12 — no fetch-execute pattern (regression guard vs phase-0 canary gh api | bash / curl | bash)
echo "A12: no fetch-execute pattern"
if python3 - "$FILE" <<'PYEOF'
import json, sys
text = open(sys.argv[1]).read()
assert "gh api" not in text, \
    "managed-settings.json must NOT contain 'gh api' (fetch-execute regression guard)"
assert "| bash" not in text, \
    "managed-settings.json must NOT contain '| bash' (fetch-execute regression guard)"
assert "| sh" not in text, \
    "managed-settings.json must NOT contain '| sh' (fetch-execute regression guard)"
PYEOF
then
  pass "A12 no fetch-execute pattern (no 'gh api', no '| bash', no '| sh')"
else
  fail "A12 fetch-execute pattern detected (regression vs phase-0 canary)"
fi

echo ""
echo "=== Results: $PASS passed, $FAIL failed ==="
if [ "$FAIL" -gt 0 ]; then
  printf "$ERRORS\n"
  exit 1
fi
exit 0
