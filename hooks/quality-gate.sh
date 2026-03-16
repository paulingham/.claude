#!/bin/bash
# Quality Gate Hook - Final check before PR creation
# PreToolUse hook for Bash commands containing "gh pr create"
#
# This is the HARD BLOCK before PR creation:
# - All tests must pass (Ruby, Node, Python)
# - No uncommitted changes (optional warning)
# - Linting must be clean (Rubocop, ESLint, Ruff)
# - Coverage >= 80%
# - Dependencies audited for vulnerabilities
# - Contract tests run (if they exist)

set -e

TOOL_NAME="${CLAUDE_TOOL_NAME:-}"
COMMAND="${CLAUDE_COMMAND:-}"

# Only check Bash commands
if [[ "$TOOL_NAME" != "Bash" ]]; then
    exit 0
fi

# Only check PR creation commands
if [[ ! "$COMMAND" =~ "gh pr create" ]]; then
    exit 0
fi

echo "QUALITY GATE: Running pre-PR checks..." >&2

FAILED=0

# Check 1: All tests must pass
echo "  Checking tests..." >&2
if command -v bundle &> /dev/null && [[ -f "Gemfile" ]]; then
    TEST_OUTPUT=$(bundle exec rspec --format progress 2>&1) || {
        echo "  FAILED: RSpec tests are not passing" >&2
        echo "$TEST_OUTPUT" | tail -10 >&2
        FAILED=1
    }
    if [[ $FAILED -eq 0 ]]; then
        echo "  PASSED: All RSpec tests green" >&2
    fi
elif [[ -f "pyproject.toml" ]] || [[ -f "pytest.ini" ]] || [[ -f "setup.cfg" ]]; then
    if command -v pytest &> /dev/null; then
        TEST_OUTPUT=$(pytest --tb=short 2>&1) || {
            echo "  FAILED: pytest tests are not passing" >&2
            echo "$TEST_OUTPUT" | tail -10 >&2
            FAILED=1
        }
        if [[ $FAILED -eq 0 ]]; then
            echo "  PASSED: All pytest tests green" >&2
        fi
    else
        echo "  SKIPPED: pytest not found" >&2
    fi
elif command -v npm &> /dev/null && [[ -f "package.json" ]]; then
    if ! npm test 2>&1 | tail -5; then
        echo "  FAILED: npm tests are not passing" >&2
        FAILED=1
    else
        echo "  PASSED: All npm tests green" >&2
    fi
else
    echo "  SKIPPED: No test runner detected" >&2
fi

# Check 2: No uncommitted changes (warning only)
echo "  Checking git status..." >&2
if [[ -n "$(git status --porcelain)" ]]; then
    echo "  WARNING: Uncommitted changes detected" >&2
    git status --short >&2
    echo "  Please commit all changes before creating PR" >&2
fi

# Check 3: Linting (Rubocop, ESLint, Ruff)
if command -v bundle &> /dev/null && [[ -f "Gemfile" ]]; then
    if bundle exec rubocop --version &> /dev/null; then
        echo "  Running Rubocop..." >&2
        RUBOCOP_OUTPUT=$(bundle exec rubocop --format simple --fail-level E 2>&1) || {
            EXIT_CODE=$?
            if [[ $EXIT_CODE -ne 0 ]]; then
                echo "  FAILED: Rubocop errors detected" >&2
                echo "$RUBOCOP_OUTPUT" | tail -15 >&2
                FAILED=1
            fi
        }
        if [[ $FAILED -eq 0 ]]; then
            echo "  PASSED: Rubocop clean" >&2
        fi
    fi
fi

if [[ -f "package.json" ]]; then
    if npx eslint --version &> /dev/null 2>&1; then
        echo "  Running ESLint..." >&2
        ESLINT_OUTPUT=$(npx eslint . --max-warnings 0 2>&1) || {
            echo "  FAILED: ESLint errors detected" >&2
            echo "$ESLINT_OUTPUT" | tail -15 >&2
            FAILED=1
        }
        if [[ $FAILED -eq 0 ]]; then
            echo "  PASSED: ESLint clean" >&2
        fi
    fi
fi

if [[ -f "pyproject.toml" ]] || [[ -f "requirements.txt" ]]; then
    if command -v ruff &> /dev/null; then
        echo "  Running Ruff..." >&2
        RUFF_OUTPUT=$(ruff check . 2>&1) || {
            echo "  FAILED: Ruff errors detected" >&2
            echo "$RUFF_OUTPUT" | tail -15 >&2
            FAILED=1
        }
        if [[ $FAILED -eq 0 ]]; then
            echo "  PASSED: Ruff clean" >&2
        fi
    fi
fi

# Check 4: Coverage check (simplecov or coverage.json)
if [[ -f "coverage/.last_run.json" ]]; then
    echo "  Checking coverage..." >&2
    COVERAGE=$(cat coverage/.last_run.json | jq -r '.result.line // 0' 2>/dev/null || echo "0")
    THRESHOLD=80
    if (( $(echo "$COVERAGE < $THRESHOLD" | bc -l 2>/dev/null || echo "0") )); then
        echo "  FAILED: Coverage ${COVERAGE}% is below ${THRESHOLD}% threshold" >&2
        FAILED=1
    else
        echo "  PASSED: Coverage ${COVERAGE}% meets threshold" >&2
    fi
fi

# Check 5: Dependency audit
echo "  Checking dependencies..." >&2
if command -v bundle &> /dev/null && [[ -f "Gemfile.lock" ]]; then
    if bundle exec bundler-audit --version &> /dev/null 2>&1; then
        AUDIT_OUTPUT=$(bundle exec bundler-audit check 2>&1) || {
            echo "  FAILED: Ruby dependency vulnerabilities found" >&2
            echo "$AUDIT_OUTPUT" | tail -10 >&2
            FAILED=1
        }
        if [[ $FAILED -eq 0 ]]; then
            echo "  PASSED: Ruby dependencies clean" >&2
        fi
    fi
fi

if [[ -f "package-lock.json" ]]; then
    AUDIT_OUTPUT=$(npm audit --audit-level=high 2>&1) || {
        echo "  FAILED: npm dependency vulnerabilities found (high+)" >&2
        echo "$AUDIT_OUTPUT" | tail -10 >&2
        FAILED=1
    }
    if [[ $FAILED -eq 0 ]]; then
        echo "  PASSED: npm dependencies clean" >&2
    fi
fi

if command -v pip-audit &> /dev/null && [[ -f "requirements.txt" ]]; then
    AUDIT_OUTPUT=$(pip-audit 2>&1) || {
        echo "  FAILED: Python dependency vulnerabilities found" >&2
        echo "$AUDIT_OUTPUT" | tail -10 >&2
        FAILED=1
    }
    if [[ $FAILED -eq 0 ]]; then
        echo "  PASSED: Python dependencies clean" >&2
    fi
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
    if [[ -f "Gemfile" ]]; then
        CONTRACT_OUTPUT=$(bundle exec rspec "$CONTRACT_DIR" 2>&1) || {
            echo "  FAILED: Contract tests failing" >&2
            echo "$CONTRACT_OUTPUT" | tail -10 >&2
            FAILED=1
        }
    elif [[ -f "package.json" ]]; then
        CONTRACT_OUTPUT=$(npx jest "$CONTRACT_DIR" 2>&1) || {
            echo "  FAILED: Contract tests failing" >&2
            echo "$CONTRACT_OUTPUT" | tail -10 >&2
            FAILED=1
        }
    elif command -v pytest &> /dev/null; then
        CONTRACT_OUTPUT=$(pytest "$CONTRACT_DIR" 2>&1) || {
            echo "  FAILED: Contract tests failing" >&2
            echo "$CONTRACT_OUTPUT" | tail -10 >&2
            FAILED=1
        }
    fi
    if [[ $FAILED -eq 0 ]]; then
        echo "  PASSED: Contract tests green" >&2
    fi
fi

if [[ $FAILED -eq 1 ]]; then
    echo "" >&2
    echo "QUALITY GATE FAILED: Fix issues before creating PR" >&2
    echo "" >&2
    echo "Required before PR:" >&2
    echo "  1. All tests must pass" >&2
    echo "  2. No linting errors (Rubocop/ESLint/Ruff)" >&2
    echo "  3. All changes committed" >&2
    echo "  4. Dependencies audited" >&2
    echo "  5. Contract tests passing (if present)" >&2
    exit 2  # Block PR creation
fi

echo "QUALITY GATE PASSED: Proceeding with PR creation" >&2
exit 0
