#!/usr/bin/env bash
# CI-BRIDGE: run by tests/shell/bridge_mcp_capability_detect.bats
# Tests for hooks/mcp-capability-detect.sh + _lib/mcp_capability.py —
# the SessionStart MCP capability detection layer.
#
# Exercises the Python parser directly (hermetic, no real `claude` call needed):
#   - feed a fake `claude mcp list` output, assert manifest written + classified
#   - degrade path (empty/failed input → all-absent manifest, exit 0)
#
# Run from repo root: bash hooks/tests/test-mcp-capability-detect.sh

set -uo pipefail

HOOKS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LIB="$HOOKS_DIR/_lib"
PASS=0
FAIL=0

pass() { echo "  PASS: $1"; PASS=$(( PASS + 1 )); }
fail() { echo "  FAIL: $1 (expected=$2, got=$3)"; FAIL=$(( FAIL + 1 )); }

run_test() {
  local name="$1" expected="$2" actual="$3"
  if [[ "$actual" -eq "$expected" ]]; then pass "$name"; else fail "$name" "$expected" "$actual"; fi
}

echo "=== mcp-capability-detect Test Harness ==="
echo ""

# ---------------------------------------------------------------------------
# Syntax check
# ---------------------------------------------------------------------------
echo "-- syntax check --"
bash -n "$HOOKS_DIR/mcp-capability-detect.sh"
run_test "bash -n mcp-capability-detect.sh -> exit 0" 0 $?
python3 -m py_compile "$LIB/mcp_capability.py"
run_test "py_compile mcp_capability.py -> exit 0" 0 $?
python3 -m py_compile "$LIB/capability_advisory.py"
run_test "py_compile capability_advisory.py -> exit 0" 0 $?
python3 -m py_compile "$LIB/design_source_adapter.py"
run_test "py_compile design_source_adapter.py -> exit 0" 0 $?
echo ""

# ---------------------------------------------------------------------------
# AC1/AC1b/AC1c/AC1d: parser handles real-world output correctly
# ---------------------------------------------------------------------------
echo "-- AC1: parser handles real-world mcp list output --"

PARSE_OUT=$(PYTHONPATH="$LIB" python3 - <<'PY'
import mcp_capability as mc

# Real-world shaped input: preamble + dedup pair + footer.
# WHY: build unicode strings at runtime so the script file stays ASCII-safe.
connected = "✔ Connected"
needs_auth = "! Needs authentication"
pending = "⏸ Pending approval (run `claude` to approve)"
preamble = "Checking MCP server health…"
tree_branch = " ├"

lines = [
    preamble, "",
    "claude.ai Google Drive: https://drivemcp.googleapis.com/mcp/v1 - " + connected,
    "claude.ai Gmail: https://gmailmcp.googleapis.com/mcp/v1 - " + needs_auth,
    "plugin:harness:lsp-typescript: python3 /abs/lsp-bridge-server.py --language ts - " + connected,
    "lsp-typescript: python3 ${CLAUDE_PLUGIN_ROOT}/hooks/_lib/lsp-bridge-server.py --language ts - " + pending,
    "",
    "MCP Config Diagnostics", "",
    "For help configuring MCP servers, see: https://example.com",
    "[Contains warnings] Project config",
    tree_branch + " [Warning] Missing environment variables: CLAUDE_PLUGIN_ROOT", "",
]
fake_output = "\n".join(lines)

servers = mc.parse_mcp_list(fake_output)
names = [s["name"] for s in servers]
statuses = {s["name"]: mc.normalize_status(s["status_raw"]) for s in servers}
lsp = next((s for s in servers if s["name"] == "plugin:harness:lsp-typescript"), None)

failures = []
if "plugin:harness:lsp-typescript" not in names:
    failures.append("prefixed lsp-typescript should be present")
if "lsp-typescript" in names:
    failures.append("bare lsp-typescript shadow should be dropped by dedup")
if statuses.get("plugin:harness:lsp-typescript") != "connected":
    failures.append("lsp-typescript status should be connected, got: " + str(statuses.get("plugin:harness:lsp-typescript")))
if statuses.get("claude.ai Gmail") != "needs-auth":
    failures.append("gmail status should be needs-auth, got: " + str(statuses.get("claude.ai Gmail")))
if lsp is None or "--language ts" not in lsp.get("endpoint", ""):
    failures.append("flagged endpoint should preserve --language ts flag")

print("OK" if not failures else "BAD: " + "; ".join(failures))
PY
)
if [[ "$PARSE_OUT" == "OK" ]]; then
  pass "parser: preamble stripped, dedup, status normalised, flagged endpoint safe"
else
  fail "parser" "OK" "$PARSE_OUT"
fi

echo ""

# ---------------------------------------------------------------------------
# AC4: build_manifest writes valid JSON to disk with expected shape
# ---------------------------------------------------------------------------
echo "-- AC4: build_manifest writes valid manifest to disk --"

MFT_TMP=$(mktemp -d)
MFT_PATH="$MFT_TMP/manifest.json"

MANIFEST_OUT=$(PYTHONPATH="$LIB" MFT_PATH="$MFT_PATH" python3 - <<'PY'
import json, os, mcp_capability as mc

mft_path = os.environ["MFT_PATH"]
connected = "✔ Connected"
servers = [
    {"name": "plugin:harness:lsp-typescript", "endpoint": "/abs/path", "status_raw": connected, "tools": []},
    {"name": "DesignSync", "endpoint": "python3 /path/ds.py", "status_raw": connected, "tools": []},
    {"name": "mystery-box", "endpoint": "/path", "status_raw": connected, "tools": []},
]
rules = mc.load_seed_rules()
manifest = mc.build_manifest(servers, rules, overrides={})
mc.write_manifest(manifest, mft_path)

data = json.loads(open(mft_path).read())
failures = []
if data.get("schema_version") != 1:
    failures.append("schema_version != 1")
if "lsp-nav" not in data.get("capabilities", {}):
    failures.append("lsp-nav not in capabilities")
if "design-source" not in data.get("capabilities", {}):
    failures.append("design-source not in capabilities")
if not any(u["server"] == "mystery-box" for u in data.get("unclassified", [])):
    failures.append("mystery-box not in unclassified")
print("OK" if not failures else "BAD: " + "; ".join(failures))
PY
)
if [[ "$MANIFEST_OUT" == "OK" ]]; then
  pass "build_manifest writes valid JSON with capabilities + unclassified"
else
  fail "build_manifest" "OK" "$MANIFEST_OUT"
fi
rm -rf "$MFT_TMP"

echo ""

# ---------------------------------------------------------------------------
# Degrade path: empty/failed claude output → all-absent manifest, no error
# ---------------------------------------------------------------------------
echo "-- degrade: empty input (failing claude) -> all-absent manifest, exit 0 --"

DEG_TMP=$(mktemp -d)
DEG_PATH="$DEG_TMP/manifest.json"

DEGRADE_OUT=$(PYTHONPATH="$LIB" DEG_PATH="$DEG_PATH" python3 - <<'PY'
import json, os, mcp_capability as mc

deg_path = os.environ["DEG_PATH"]
# Simulate `claude mcp list` failing: empty string input
servers = mc.parse_mcp_list("")
manifest = mc.build_manifest(servers, mc.load_seed_rules(), overrides={})
mc.write_manifest(manifest, deg_path)

data = json.loads(open(deg_path).read())
failures = []
if data.get("schema_version") != 1:
    failures.append("schema_version != 1")
if data.get("capabilities", {}) != {}:
    failures.append("capabilities should be empty, got: " + str(data.get("capabilities")))
if data.get("unclassified", []) != []:
    failures.append("unclassified should be empty, got: " + str(data.get("unclassified")))
print("OK" if not failures else "BAD: " + "; ".join(failures))
PY
)
EXIT_CODE=$?
if [[ "$DEGRADE_OUT" == "OK" ]]; then
  pass "degrade: empty input -> empty capabilities manifest, no error"
else
  fail "degrade: empty input -> empty capabilities manifest" "OK" "$DEGRADE_OUT"
fi
run_test "degrade: python exits 0 (never fail-closed)" 0 "$EXIT_CODE"
rm -rf "$DEG_TMP"

echo ""

# ---------------------------------------------------------------------------
# AC2/AC3: classification engine (name_regex, tool_family, override)
# ---------------------------------------------------------------------------
echo "-- AC2/AC3: classification engine --"

CLASSIFY_OUT=$(PYTHONPATH="$LIB" python3 - <<'PY'
import mcp_capability as mc

rules = mc.load_seed_rules()
ok = True

# name_regex: DesignSync -> design-source
ok &= mc.classify_server({"name": "DesignSync", "tools": []}, rules, {}) == "design-source"

# name_regex: jira -> issue-tracker
ok &= mc.classify_server({"name": "jira-bridge", "tools": []}, rules, {}) == "issue-tracker"

# tool_family fallback (custom name, no regex)
ok &= mc.classify_server({"name": "custom-tracker", "tools": ["move_card_to_list"]}, rules, {}) == "issue-tracker"

# override wins over seed
ok &= mc.classify_server({"name": "my-server", "tools": []}, rules, {"my-server": "design-source"}) == "design-source"

# unknown -> unclassified
ok &= mc.classify_server({"name": "unknown-xyz", "tools": []}, rules, {}) == "unclassified"

print("OK" if ok else "BAD")
PY
)
if [[ "$CLASSIFY_OUT" == "OK" ]]; then
  pass "classification: name_regex, tool_family, override, unclassified all correct"
else
  fail "classification engine" "OK" "$CLASSIFY_OUT"
fi

echo ""

# ---------------------------------------------------------------------------
# Real `claude mcp list` round-trip: parser handles live output without error
# ---------------------------------------------------------------------------
echo "-- live claude mcp list round-trip (advisory, no assertion on count) --"

MCP_TMPFILE=$(mktemp)
claude mcp list >"$MCP_TMPFILE" 2>/dev/null || true
ROUNDTRIP_OUT=$(PYTHONPATH="$LIB" MCP_TMPFILE="$MCP_TMPFILE" python3 - <<'PY'
import os, mcp_capability as mc
raw = open(os.environ["MCP_TMPFILE"]).read()
try:
    servers = mc.parse_mcp_list(raw)
    print("OK: {} servers".format(len(servers)))
except Exception as e:
    print("BAD: {}".format(e))
PY
)
rm -f "$MCP_TMPFILE"
if echo "$ROUNDTRIP_OUT" | grep -q "^OK:"; then
  pass "live claude mcp list round-trip: $ROUNDTRIP_OUT"
else
  fail "live claude mcp list round-trip" "OK: N servers" "$ROUNDTRIP_OUT"
fi

echo ""

echo "=== Results: $PASS passed, $FAIL failed ==="
[[ $FAIL -gt 0 ]] && exit 1
exit 0
