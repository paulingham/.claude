#!/usr/bin/env bash
# test-hooks-json.sh — ACs for plugin-port-slice3
# A1  hooks.json exists + valid JSON
# A2  .claude-plugin/plugin.json has "hooks": "./hooks/hooks.json"
# A3  registered hook count == 88
# A4  every /hooks/-referencing arg uses ${CLAUDE_PLUGIN_ROOT:-
# A5  ZERO residual bare ${CLAUDE_CONFIG_DIR:-$HOME/.claude}/hooks/ in hooks.json
# A6  ZERO hcom / rtk / gh-cache strings in hooks.json
# A7  spot-check: >=3 hooks keep settings.json matcher+timeout

set -uo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

PASS=0
FAIL=0
pass() { echo "  PASS: $1"; PASS=$((PASS+1)); }
fail() { echo "  FAIL: $1"; FAIL=$((FAIL+1)); }

HOOKS_JSON="$REPO_ROOT/hooks/hooks.json"
PLUGIN_JSON="$REPO_ROOT/.claude-plugin/plugin.json"
SETTINGS_JSON="$REPO_ROOT/settings.json"

echo "-- hooks/hooks.json (A1-A7) --"

# A1: hooks.json exists and is valid JSON
if [[ ! -f "$HOOKS_JSON" ]]; then
    fail "A1: hooks.json missing"
else
    if python3 -m json.tool < "$HOOKS_JSON" > /dev/null 2>&1; then
        pass "A1: hooks.json exists and is valid JSON"
    else
        fail "A1: hooks.json exists but is invalid JSON"
    fi
fi

# A2: plugin.json has "hooks": "./hooks/hooks.json"
if [[ ! -f "$PLUGIN_JSON" ]]; then
    fail "A2: .claude-plugin/plugin.json missing"
else
    hooks_field=$(python3 -c "import json; d=json.load(open('$PLUGIN_JSON')); print(d.get('hooks','MISSING'))")
    if [[ "$hooks_field" == "./hooks/hooks.json" ]]; then
        pass "A2: plugin.json has hooks: ./hooks/hooks.json"
    else
        fail "A2: plugin.json hooks field is '$hooks_field' (expected './hooks/hooks.json')"
    fi
fi

# A3: registered hook count == 88
if [[ -f "$HOOKS_JSON" ]]; then
    count=$(python3 -c "import json; d=json.load(open('$HOOKS_JSON')); total=sum(len(g.get('hooks',[])) for ev_groups in d.get('hooks',{}).values() for g in ev_groups); print(total)")
    if [[ "$count" == "88" ]]; then
        pass "A3: hook count is 88"
    else
        fail "A3: hook count is $count (expected 88)"
    fi
fi

# A4: every /hooks/-referencing arg uses ${CLAUDE_PLUGIN_ROOT:-
if [[ -f "$HOOKS_JSON" ]]; then
    bad_refs=$(python3 -c "
import json
with open('$HOOKS_JSON') as f:
    d = json.load(f)
bad = []
for ev, groups in d.get('hooks', {}).items():
    for g in groups:
        for h in g.get('hooks', []):
            for arg in h.get('args', []):
                s = str(arg)
                if '/hooks/' in s and '\${CLAUDE_PLUGIN_ROOT:-' not in s:
                    bad.append(ev + ': ' + s[:80])
print('\n'.join(bad))
")
    if [[ -z "$bad_refs" ]]; then
        pass "A4: all /hooks/-referencing args use \${CLAUDE_PLUGIN_ROOT:-"
    else
        fail "A4: found /hooks/ refs without CLAUDE_PLUGIN_ROOT:-:"
        echo "$bad_refs" | head -5
    fi
fi

# A5: ZERO residual bare ${CLAUDE_CONFIG_DIR:-$HOME/.claude}/hooks/
if [[ -f "$HOOKS_JSON" ]]; then
    # Use python to avoid shell escaping issues
    residual_count=$(python3 -c "
import json
with open('$HOOKS_JSON') as f:
    content = f.read()
import re
pattern = r'\$\{CLAUDE_CONFIG_DIR:-\\\$HOME/\.claude\}/hooks/'
matches = re.findall(pattern, content)
print(len(matches))
")
    if [[ "$residual_count" == "0" ]]; then
        pass "A5: zero residual bare CLAUDE_CONFIG_DIR/hooks/ refs"
    else
        fail "A5: found $residual_count residual bare CLAUDE_CONFIG_DIR/hooks/ refs"
    fi
fi

# A6: ZERO hcom / rtk / gh-cache strings
if [[ -f "$HOOKS_JSON" ]]; then
    a6_result=$(python3 -c "
import re
content = open('$HOOKS_JSON').read()
hcom = len(re.findall(r'hcom', content))
rtk = len(re.findall(r'[^a-z]rtk[^a-z]|\"rtk\"', content))
ghcache = len(re.findall(r'gh-cache', content))
print(str(hcom) + ' ' + str(rtk) + ' ' + str(ghcache))
")
    hcom_count=$(echo "$a6_result" | awk '{print $1}')
    rtk_count=$(echo "$a6_result" | awk '{print $2}')
    ghcache_count=$(echo "$a6_result" | awk '{print $3}')
    if [[ "$hcom_count" == "0" && "$rtk_count" == "0" && "$ghcache_count" == "0" ]]; then
        pass "A6: zero hcom/rtk/gh-cache entries"
    else
        fail "A6: hcom=$hcom_count rtk=$rtk_count gh-cache=$ghcache_count (all must be 0)"
    fi
fi

# A7: spot-check >=3 hooks keep settings.json matcher+timeout
if [[ -f "$HOOKS_JSON" && -f "$SETTINGS_JSON" ]]; then
    spot_result=$(python3 -c "
import json

with open('$SETTINGS_JSON') as f:
    settings = json.load(f)
with open('$HOOKS_JSON') as f:
    plugin = json.load(f)

# Build lookup: (event, script_name, matcher) -> timeout from settings.json
# Key includes matcher because the same script can appear under multiple matchers
settings_map = {}
for ev, groups in settings.get('hooks', {}).items():
    for g in groups:
        matcher = g.get('matcher')
        for h in g.get('hooks', []):
            args = h.get('args', [])
            if len(args) > 1 and '/hooks/' in args[1]:
                script_part = args[1].split('/hooks/')[-1].split('\"')[0]
                settings_map[(ev, script_part, matcher)] = h.get('timeout')

matches = 0
mismatches = []
for ev, groups in plugin.get('hooks', {}).items():
    for g in groups:
        matcher = g.get('matcher')
        for h in g.get('hooks', []):
            args = h.get('args', [])
            if len(args) > 1 and '/hooks/' in args[1]:
                script_part = args[1].split('/hooks/')[-1].split('\"')[0]
                key = (ev, script_part, matcher)
                if key in settings_map:
                    exp_timeout = settings_map[key]
                    if h.get('timeout') == exp_timeout:
                        matches += 1
                    else:
                        mismatches.append(ev + '/' + script_part + ' got_timeout=' + str(h.get('timeout')) + ' exp_timeout=' + str(exp_timeout))
                else:
                    mismatches.append('NOT_IN_SETTINGS: ' + ev + '/' + script_part + '/' + str(matcher))
print(str(matches) + ' ' + str(len(mismatches)))
for m in mismatches[:3]:
    print('MISMATCH: ' + m)
")
    match_count=$(echo "$spot_result" | head -1 | awk '{print $1}')
    mismatch_count=$(echo "$spot_result" | head -1 | awk '{print $2}')
    if [[ "$mismatch_count" == "0" && "${match_count:-0}" -ge "3" ]]; then
        pass "A7: $match_count hooks verified keeping settings.json matcher+timeout (0 mismatches)"
    else
        fail "A7: matches=$match_count mismatches=$mismatch_count (need >=3 matches, 0 mismatches)"
        echo "$spot_result" | tail -n +2 | head -5
    fi
fi

echo ""
echo "=== Results: $PASS passed, $FAIL failed ==="
if [[ $FAIL -gt 0 ]]; then
    exit 1
fi
exit 0
