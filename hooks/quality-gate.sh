#!/bin/bash
# Quality Gate Hook - Final check before PR creation
# PreToolUse hook for Bash commands containing "gh pr create"
#
# Project-aware: detects project type from file presence and only runs
# checks relevant to that project. Uses per-check result tracking so
# each check independently reports PASSED/FAILED.

set -e

# Hook profile (minimal — always runs as a blocking hook)
source ~/.claude/hooks/hook-profile.sh && check_hook_profile "minimal" || exit 0

INPUT=$(cat)
TOOL_NAME=$(echo "$INPUT" | jq -r '.tool_name // empty')
COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command // empty')

# Only check Bash commands
if [[ "$TOOL_NAME" != "Bash" ]]; then
    exit 0
fi

# Only check PR creation commands
if [[ ! "$COMMAND" =~ "gh pr create" ]]; then
    exit 0
fi

echo "QUALITY GATE: Running pre-PR checks..." >&2

ANY_FAILED=0

# Detect project type
IS_NODE=false
IS_RUBY=false
IS_PYTHON=false

if [[ -f "package.json" ]]; then
    IS_NODE=true
fi
if [[ -f "Gemfile" ]]; then
    IS_RUBY=true
fi
if [[ -f "pyproject.toml" ]] || [[ -f "requirements.txt" ]] || [[ -f "pytest.ini" ]] || [[ -f "setup.cfg" ]]; then
    IS_PYTHON=true
fi

# Check 1: All tests must pass
echo "  Checking tests..." >&2
TEST_RESULT=0
if [[ "$IS_RUBY" == true ]] && command -v bundle &> /dev/null; then
    TEST_OUTPUT=$(bundle exec rspec --format progress 2>&1) || {
        echo "  FAILED: RSpec tests are not passing" >&2
        echo "$TEST_OUTPUT" | tail -10 >&2
        TEST_RESULT=1
    }
elif [[ "$IS_PYTHON" == true ]] && command -v pytest &> /dev/null; then
    TEST_OUTPUT=$(pytest --tb=short 2>&1) || {
        echo "  FAILED: pytest tests are not passing" >&2
        echo "$TEST_OUTPUT" | tail -10 >&2
        TEST_RESULT=1
    }
elif [[ "$IS_NODE" == true ]] && command -v npm &> /dev/null; then
    if ! npm test 2>&1 | tail -5; then
        echo "  FAILED: npm tests are not passing" >&2
        TEST_RESULT=1
    fi
else
    echo "  SKIPPED: No test runner detected" >&2
fi
if [[ $TEST_RESULT -eq 0 ]]; then
    echo "  PASSED: All tests green" >&2
else
    ANY_FAILED=1
fi

# Check 2: No uncommitted changes (warning only)
echo "  Checking git status..." >&2
if [[ -n "$(git status --porcelain)" ]]; then
    echo "  WARNING: Uncommitted changes detected" >&2
    git status --short >&2
    echo "  Please commit all changes before creating PR" >&2
fi

# Check 3: Linting
LINT_RESULT=0
if [[ "$IS_RUBY" == true ]] && command -v bundle &> /dev/null; then
    if bundle exec rubocop --version &> /dev/null 2>&1; then
        echo "  Running Rubocop..." >&2
        RUBOCOP_OUTPUT=$(bundle exec rubocop --format simple --fail-level E 2>&1) || {
            echo "  FAILED: Rubocop errors detected" >&2
            echo "$RUBOCOP_OUTPUT" | tail -15 >&2
            LINT_RESULT=1
        }
    fi
elif [[ "$IS_NODE" == true ]]; then
    if npx eslint --version &> /dev/null 2>&1; then
        echo "  Running ESLint..." >&2
        ESLINT_OUTPUT=$(npx eslint . --max-warnings 0 2>&1) || {
            echo "  FAILED: ESLint errors detected" >&2
            echo "$ESLINT_OUTPUT" | tail -15 >&2
            LINT_RESULT=1
        }
    fi
elif [[ "$IS_PYTHON" == true ]] && command -v ruff &> /dev/null; then
    echo "  Running Ruff..." >&2
    RUFF_OUTPUT=$(ruff check . 2>&1) || {
        echo "  FAILED: Ruff errors detected" >&2
        echo "$RUFF_OUTPUT" | tail -15 >&2
        LINT_RESULT=1
    }
fi
if [[ $LINT_RESULT -eq 0 ]]; then
    echo "  PASSED: Linting clean" >&2
else
    ANY_FAILED=1
fi

# Check 4: Coverage check (simplecov or coverage.json)
if [[ -f "coverage/.last_run.json" ]]; then
    echo "  Checking coverage..." >&2
    COVERAGE=$(cat coverage/.last_run.json | jq -r '.result.line // 0' 2>/dev/null || echo "0")
    THRESHOLD=80
    if (( $(echo "$COVERAGE < $THRESHOLD" | bc -l 2>/dev/null || echo "0") )); then
        echo "  FAILED: Coverage ${COVERAGE}% is below ${THRESHOLD}% threshold" >&2
        ANY_FAILED=1
    else
        echo "  PASSED: Coverage ${COVERAGE}% meets threshold" >&2
    fi
fi

# Check 5: Dependency audit (project-type-aware)
echo "  Checking dependencies..." >&2
AUDIT_RESULT=0
if [[ "$IS_RUBY" == true ]] && [[ -f "Gemfile.lock" ]] && command -v bundle &> /dev/null; then
    if bundle exec bundler-audit --version &> /dev/null 2>&1; then
        AUDIT_OUTPUT=$(bundle exec bundler-audit check 2>&1) || {
            echo "  FAILED: Ruby dependency vulnerabilities found" >&2
            echo "$AUDIT_OUTPUT" | tail -10 >&2
            AUDIT_RESULT=1
        }
    fi
elif [[ "$IS_NODE" == true ]] && [[ -f "package-lock.json" ]]; then
    AUDIT_OUTPUT=$(npm audit --audit-level=high 2>&1) || {
        echo "  FAILED: npm dependency vulnerabilities found (high+)" >&2
        echo "$AUDIT_OUTPUT" | tail -10 >&2
        AUDIT_RESULT=1
    }
elif [[ "$IS_PYTHON" == true ]] && [[ -f "requirements.txt" ]] && command -v pip-audit &> /dev/null; then
    AUDIT_OUTPUT=$(pip-audit 2>&1) || {
        echo "  FAILED: Python dependency vulnerabilities found" >&2
        echo "$AUDIT_OUTPUT" | tail -10 >&2
        AUDIT_RESULT=1
    }
fi
if [[ $AUDIT_RESULT -eq 0 ]]; then
    echo "  PASSED: Dependencies clean" >&2
else
    ANY_FAILED=1
fi

# Check 6: Contract tests (if they exist)
CONTRACT_DIR=""
for dir in spec/contracts test/contracts tests/contracts; do
    if [[ -d "$dir" ]]; then
        CONTRACT_DIR="$dir"
        break
    fi
done

if [[ -n "$CONTRACT_DIR" ]]; then
    echo "  Running contract tests ($CONTRACT_DIR)..." >&2
    CONTRACT_RESULT=0
    if [[ "$IS_RUBY" == true ]]; then
        CONTRACT_OUTPUT=$(bundle exec rspec "$CONTRACT_DIR" 2>&1) || {
            echo "  FAILED: Contract tests failing" >&2
            echo "$CONTRACT_OUTPUT" | tail -10 >&2
            CONTRACT_RESULT=1
        }
    elif [[ "$IS_NODE" == true ]]; then
        CONTRACT_OUTPUT=$(npx jest "$CONTRACT_DIR" 2>&1) || {
            echo "  FAILED: Contract tests failing" >&2
            echo "$CONTRACT_OUTPUT" | tail -10 >&2
            CONTRACT_RESULT=1
        }
    elif [[ "$IS_PYTHON" == true ]] && command -v pytest &> /dev/null; then
        CONTRACT_OUTPUT=$(pytest "$CONTRACT_DIR" 2>&1) || {
            echo "  FAILED: Contract tests failing" >&2
            echo "$CONTRACT_OUTPUT" | tail -10 >&2
            CONTRACT_RESULT=1
        }
    fi
    if [[ $CONTRACT_RESULT -eq 0 ]]; then
        echo "  PASSED: Contract tests green" >&2
    else
        ANY_FAILED=1
    fi
fi

# Check 7: Code shape validation (source files only)
echo "  Checking code shape..." >&2
SHAPE_RESULT=0
if command -v git &> /dev/null; then
    CHANGED_FILES=$(git diff --name-only HEAD~1 HEAD 2>/dev/null | grep -E '\.(ts|tsx|js|jsx)$' | grep -vE '\.(test|spec)\.' | grep -vE '(__tests__|/test/|/tests/|/e2e/)' | grep -vE '\.(config)\.' | grep -vE '(tailwind|babel|metro|jest|eslint|prettier)' || true)

    for file in $CHANGED_FILES; do
        if [[ -f "$file" ]]; then
            LINES=$(wc -l < "$file" | tr -d ' ')
            if [[ "$LINES" -gt 50 ]]; then
                echo "  FAILED: $file has $LINES lines (limit: 50)" >&2
                SHAPE_RESULT=1
            fi
        fi
    done
fi
if [[ $SHAPE_RESULT -eq 0 ]]; then
    echo "  PASSED: All source files within shape limits" >&2
else
    echo "  FAILED: Code shape violations detected -- decompose files before PR" >&2
    ANY_FAILED=1
fi

# Check 8: Maestro E2E (advisory — requires simulator)
if [[ -d "maestro" ]] && command -v maestro &> /dev/null; then
    echo "  Checking E2E trigger criteria..." >&2
    E2E_TRIGGER_FILES=$(git diff --name-only HEAD~1 HEAD 2>/dev/null | grep -E \
        '(url-classification|url-parse-helpers|constants|navigation-helpers|useNavigationHandler|navigationCallbacks|session-store|session-message-handler|useWebViewAuth|useWebViewMessages|useBiometricGating|useBiometricState|biometric-auth|WebViewContainer|WebViewScreen|NetworkBanner|useNetworkStatus|file-download|cookie-manager|viewport-meta|session-check|_layout|index)\.(ts|tsx)$' \
        || true)

    if [[ -n "$E2E_TRIGGER_FILES" ]]; then
        if xcrun simctl list devices 2>/dev/null | grep -q "Booted"; then
            echo "  Running Maestro E2E..." >&2
            if maestro test maestro/ 2>&1 | tail -5; then
                echo "  PASSED: Maestro E2E flows green" >&2
            else
                echo "  WARNING: Maestro E2E flows failed (advisory)" >&2
            fi
        else
            echo "  SKIPPED: E2E triggered but no booted simulator found" >&2
        fi
    else
        echo "  SKIPPED: No E2E trigger files in diff" >&2
    fi
else
    echo "  SKIPPED: Maestro not installed or no maestro/ directory" >&2
fi

if [[ $ANY_FAILED -eq 1 ]]; then
    echo "" >&2
    echo "QUALITY GATE FAILED: Fix issues before creating PR" >&2
    exit 2
fi

echo "QUALITY GATE PASSED: Proceeding with PR creation" >&2
exit 0
