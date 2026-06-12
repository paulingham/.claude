#!/usr/bin/env bash
# test-hook-registration-invariant.sh — ACs for ws-e-dead-hooks-audit
# AC1  probe hook and orphaned test files deleted
# AC2  every hooks/*.sh is registered in settings.json or hooks.json (or allowlisted/exempted)
# AC3  undocumented hooks (rtk, reflect-*) added to README hook table

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

PASS=0
FAIL=0
pass() { echo "  PASS: $1"; PASS=$((PASS+1)); }
fail() { echo "  FAIL: $1"; FAIL=$((FAIL+1)); }

# python3 availability guard
if ! command -v python3 > /dev/null 2>&1; then
    echo "SKIP: python3 required but not found"
    exit 0
fi

# ---------------------------------------------------------------------------
# Exemption tiers (hardcoded with citations)
# ---------------------------------------------------------------------------

# Tier 1 — sourced library functions (not event hooks; sourced via `. script`)
SOURCED_LIBS_LIST="hook-profile.sh loop-guard.sh"
# hook-profile.sh — sourced by: hooks/code-shape-check.sh:16, hooks/tdd-guard.sh:18 et al.
# loop-guard.sh   — sourced by: hooks/tdd-guard.sh:32, hooks/code-shape-check.sh:17

# Tier 2 — protocol/skill-invoked (orchestrator calls directly; not event-registered)
# Format: "script_basename|citation"
ALLOWLIST_LIST="pipeline-analytics.sh|skills/pipeline/SKILL.md:633 (Step 7a Reflect analytics)
reflect-gate-acknowledgment.sh|protocols/reflection-protocol.md:137 (Reflect 6d-bis gate)
reflect-token-emit.sh|protocols/reflection-protocol.md:139 (deviation token writer)
phase-boundary-compress.sh|skills/pipeline/SKILL.md:299 (phase-boundary token analytics)
cloud-bootstrap.sh|hooks/cloud-bootstrap.sh:9-12 (operator-deployed cloud utility; not wired in shipped configs by design)"
# Tier 3 — hooks/tests/ directory contents: excluded by path filter
# Tier 4 — hooks/_lib/ contents: excluded by path filter

# ---------------------------------------------------------------------------
# AC1: probe hook and orphaned test files deleted
# ---------------------------------------------------------------------------
echo "-- AC1: probe cleanup --"

# stub: probe hook file does not exist
if [[ ! -f "$REPO_ROOT/hooks/probe-modified-tool-input.sh" ]]; then
    pass "probe hook file does not exist"
else
    fail "probe hook file does not exist"
fi

# stub: probe test file does not exist
if [[ ! -f "$REPO_ROOT/tests/test_probe_script.py" ]]; then
    pass "probe test file does not exist"
else
    fail "probe test file does not exist"
fi

# stub: probe artifact test file does not exist
if [[ ! -f "$REPO_ROOT/tests/test_probe_artifact.py" ]]; then
    pass "probe artifact test file does not exist"
else
    fail "probe artifact test file does not exist"
fi

# stub: no live non-proposal probe references
live_refs=$(grep -r "probe-modified-tool-input" "$REPO_ROOT" \
    --exclude-dir=".git" \
    --include="*.sh" --include="*.py" --include="*.md" --include="*.json" \
    --include="*.yml" --include="*.yaml" --include="*.txt" \
    2>/dev/null \
    | grep -v "protocols/_proposals/" \
    | grep -v "learning/instincts/" \
    | grep -v "hooks/tests/test-hook-registration-invariant.sh" \
    | wc -l | tr -d ' ')
if [[ "$live_refs" == "0" ]]; then
    pass "no live non-proposal probe references"
else
    fail "no live non-proposal probe references ($live_refs found)"
fi

# ---------------------------------------------------------------------------
# AC2: every hooks/*.sh is registered or allowlisted
# ---------------------------------------------------------------------------
echo "-- AC2: hook registration invariant --"

# stub: hook count is positive before invariant runs
hook_count=$(find "$REPO_ROOT/hooks" -maxdepth 1 -name "*.sh" | wc -l | tr -d ' ')
if [[ "$hook_count" -gt 0 ]]; then
    pass "hook count is positive before invariant runs ($hook_count hooks)"
else
    fail "hook count is positive before invariant runs (got 0 — check REPO_ROOT)"
fi

# Helper: check_hooks_invariant <hooks_dir>
# Returns 0 (pass) or 1 (fail); prints unregistered basenames on failure.
check_hooks_invariant() {
    local dir="$1"
    local settings_json="$REPO_ROOT/settings.json"
    local hooks_json="$REPO_ROOT/hooks/hooks.json"

    local registered_scripts
    registered_scripts=$(python3 - "$settings_json" "$hooks_json" <<'PYEOF'
import json, re, sys

def extract_basenames(path):
    try:
        with open(path) as f:
            content = f.read()
        d = json.loads(content)
    except Exception:
        print(f"WARN: cannot parse {path}", file=sys.stderr)
        return set()
    basenames = set()
    def walk(obj):
        if isinstance(obj, dict):
            for v in obj.values():
                walk(v)
        elif isinstance(obj, list):
            for item in obj:
                walk(item)
        elif isinstance(obj, str):
            # match /hooks/something.sh or hooks/something.sh
            for m in re.findall(r'(?:^|[/ ])([a-zA-Z0-9_-]+\.sh)', obj):
                basenames.add(m)
    walk(d)
    return basenames

s1 = extract_basenames(sys.argv[1])
s2 = extract_basenames(sys.argv[2])
all_names = s1 | s2
print('\n'.join(sorted(all_names)))
PYEOF
)

    # Guard: if both sources yielded zero basenames, the read is broken
    if [[ -z "$registered_scripts" ]]; then
        echo "ERROR: extract_basenames returned empty set for both $settings_json and $hooks_json — broken read" >&2
        return 1
    fi

    local unregistered=()
    while IFS= read -r hook_path; do
        local base
        base="$(basename "$hook_path")"

        # Tier 3: skip hooks/tests/ contents
        case "$hook_path" in
            */hooks/tests/*) continue ;;
        esac

        # Tier 4: skip hooks/_lib/ contents
        case "$hook_path" in
            */hooks/_lib/*) continue ;;
        esac

        # Tier 1: skip SOURCED_LIBS
        local is_sourced=0
        while IFS= read -r lib; do
            if [[ "$base" == "$lib" ]]; then
                is_sourced=1
                break
            fi
        done < <(printf '%s\n' $SOURCED_LIBS_LIST)
        if [[ "$is_sourced" -eq 1 ]]; then
            continue
        fi

        # Tier 2: skip ALLOWLIST entries
        local is_allowlisted=0
        while IFS= read -r entry; do
            local entry_base="${entry%%|*}"
            if [[ "$base" == "$entry_base" ]]; then
                is_allowlisted=1
                break
            fi
        done <<< "$ALLOWLIST_LIST"
        if [[ "$is_allowlisted" -eq 1 ]]; then
            continue
        fi

        # Check registration
        local found=0
        while IFS= read -r reg; do
            if [[ "$base" == "$reg" ]]; then
                found=1
                break
            fi
        done <<< "$registered_scripts"

        if [[ "$found" -eq 0 ]]; then
            unregistered+=("$base")
        fi
    done < <(find "$dir" -maxdepth 1 -name "*.sh" 2>/dev/null | sort)

    if [[ "${#unregistered[@]}" -eq 0 ]]; then
        return 0
    else
        echo "unregistered: ${unregistered[*]}"
        return 1
    fi
}

# stub: every hooks-sh is registered or allowlisted
result=$(check_hooks_invariant "$REPO_ROOT/hooks" 2>&1)
exit_code=$?
if [[ $exit_code -eq 0 ]]; then
    pass "every hooks-sh is registered or allowlisted"
else
    fail "every hooks-sh is registered or allowlisted ($result)"
fi

# stub: allowlist entries carry citations
citation_ok=1
while IFS= read -r entry; do
    citation="${entry#*|}"
    if [[ -z "${citation// /}" ]]; then
        fail "allowlist entries carry citations (empty citation for: ${entry%%|*})"
        citation_ok=0
    fi
done <<< "$ALLOWLIST_LIST"
if [[ "$citation_ok" -eq 1 ]]; then
    pass "allowlist entries carry citations"
fi

# stub: canary unregistered hook triggers failure
canary_dir=$(mktemp -d 2>/dev/null || mktemp -d -t "canary" 2>/dev/null)
if [[ -z "$canary_dir" ]]; then
    fail "canary unregistered hook triggers failure (mktemp failed)"
else
    trap 'rm -rf "$canary_dir"' EXIT
    cp "$REPO_ROOT/hooks/session-start-bootstrap.sh" "$canary_dir/canary-unregistered-hook.sh" 2>/dev/null || \
        printf '#!/usr/bin/env bash\necho canary\n' > "$canary_dir/canary-unregistered-hook.sh"
    chmod +x "$canary_dir/canary-unregistered-hook.sh"

    canary_output=$(check_hooks_invariant "$canary_dir" 2>&1)
    canary_exit=$?
    if [[ "$canary_exit" -ne 0 ]] && echo "$canary_output" | grep -q "canary-unregistered-hook.sh"; then
        pass "canary unregistered hook triggers failure"
    else
        fail "canary unregistered hook triggers failure (exit=$canary_exit output=$canary_output)"
    fi
fi

# ---------------------------------------------------------------------------
# AC3: README hook table rows present
# ---------------------------------------------------------------------------
echo "-- AC3: README documentation --"

README="$REPO_ROOT/README.md"

# stub: rtk documented in README hook table
if grep -q "rtk" "$README" 2>/dev/null; then
    pass "rtk documented in README hook table"
else
    fail "rtk documented in README hook table"
fi

# stub: rtk row mentions absent-binary behavior
if grep -A5 "rtk" "$README" 2>/dev/null | grep -qi "absent\|missing\|not.*found\|proceeds.*without\|without.*interception"; then
    pass "rtk row mentions absent-binary behavior"
else
    fail "rtk row mentions absent-binary behavior"
fi

# stub: reflect-gate-acknowledgment documented in README
if grep -q "reflect-gate-acknowledgment" "$README" 2>/dev/null; then
    pass "reflect-gate-acknowledgment documented in README"
else
    fail "reflect-gate-acknowledgment documented in README"
fi

# stub: reflect-token-emit documented in README
if grep -q "reflect-token-emit" "$README" 2>/dev/null; then
    pass "reflect-token-emit documented in README"
else
    fail "reflect-token-emit documented in README"
fi

# ---------------------------------------------------------------------------
echo ""
echo "=== Results: $PASS passed, $FAIL failed ==="
if [[ $FAIL -gt 0 ]]; then
    exit 1
fi
exit 0
