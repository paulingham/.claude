#!/usr/bin/env bats
# Slice-a parser-widen edge tests.
#
# A2: _qg_extract_intake_tier accepts T3H, rejects T0H/T6H/T3.5/garbage.
# A3: Python _INTAKE_TIER_RE (pipeline_entry_guard_cli.py:21) uses alternation
#     so T0H..T6H are NOT matched (proves H? form absent).

setup() {
  REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
  CHECKS_SH="$REPO_ROOT/hooks/_lib/quality-gate-checks.sh"
  GUARD_CLI="$REPO_ROOT/hooks/_lib/pipeline_entry_guard_cli.py"
  TMP_DIR="$(mktemp -d -t t3h-detector-edges-XXXXXX)"
}

teardown() {
  if [ -n "${TMP_DIR:-}" ] && [ -d "$TMP_DIR" ]; then
    find "$TMP_DIR" -type f -delete
    find "$TMP_DIR" -depth -type d -empty -delete
  fi
}

# --- helpers -----------------------------------------------------------------

write_intake() {
  local task="$1" tier_line="$2"
  mkdir -p "$TMP_DIR/pipeline-state/$task"
  printf '%s\n' "$tier_line" > "$TMP_DIR/pipeline-state/$task/intake.md"
}

extract_tier() {
  # WHY: source checks.sh, call extractor on the given intake path
  local intake="$1"
  bash -c "source '$CHECKS_SH' && _qg_extract_intake_tier '$intake'"
}

# --- A2: extractor accepts T3H -----------------------------------------------

@test "test_extractor_accepts_T3H_rejects_T0H_T6H_garbage" {
  # T3H must be extracted
  write_intake t3h-task 'tier_emitted: T3H'
  result=$(extract_tier "$TMP_DIR/pipeline-state/t3h-task/intake.md")
  [ "$result" = "T3H" ]

  # T0H must return empty
  write_intake t0h-task 'tier_emitted: T0H'
  result=$(extract_tier "$TMP_DIR/pipeline-state/t0h-task/intake.md")
  [ -z "$result" ]

  # T6H must return empty
  write_intake t6h-task 'tier_emitted: T6H'
  result=$(extract_tier "$TMP_DIR/pipeline-state/t6h-task/intake.md")
  [ -z "$result" ]

  # T3.5 must return empty
  write_intake t35-task 'tier_emitted: T3.5'
  result=$(extract_tier "$TMP_DIR/pipeline-state/t35-task/intake.md")
  [ -z "$result" ]

  # garbage must return empty
  write_intake garbage-task 'tier_emitted: RUBBISH'
  result=$(extract_tier "$TMP_DIR/pipeline-state/garbage-task/intake.md")
  [ -z "$result" ]
}

# --- A3: Python regex uses alternation, not H? --------------------------------

# --- E2: alternation accepts exactly 8 valid tokens, rejects H?-style tokens ---

@test "test_alternation_accepts_only_eight_valid_tokens" {
  # WHY: anti-H? guard — proves BOTH extractors accept {T0..T6,T3H} and reject
  # T0H/T6H/T3.5/T7/garbage. Any regression to (T[0-6]H?) widens acceptance
  # to T0H..T6H (except T3H already valid — but T0H/T2H/T4H/T5H/T6H would all
  # sneak through). This test catches that regression.

  # 1. Shell extractor — _qg_extract_intake_tier
  local valid_tiers="T0 T1 T2 T3 T3H T4 T5 T6"
  for tier in $valid_tiers; do
    write_intake "e2-valid-$tier" "tier_emitted: $tier"
    result=$(extract_tier "$TMP_DIR/pipeline-state/e2-valid-$tier/intake.md")
    [ "$result" = "$tier" ] || { echo "FAIL: shell extractor rejected valid tier $tier"; return 1; }
  done

  local invalid_tiers="T0H T6H T3.5 T7 RUBBISH T3h t3h"
  for tier in $invalid_tiers; do
    write_intake "e2-invalid-$tier" "tier_emitted: $tier"
    result=$(extract_tier "$TMP_DIR/pipeline-state/e2-invalid-$tier/intake.md")
    [ -z "$result" ] || { echo "FAIL: shell extractor accepted invalid tier $tier -> $result"; return 1; }
  done

  # 2. Python regex — pipeline_entry_guard_cli.py _INTAKE_TIER_RE
  local py_script="$TMP_DIR/check_eight_tokens.py"
  cat > "$py_script" <<'PYEOF'
import sys, re, ast

cli_path = sys.argv[1]
src = open(cli_path).read()
tree = ast.parse(src)
pattern_str = None
for node in ast.walk(tree):
    if isinstance(node, ast.Assign):
        for target in node.targets:
            if isinstance(target, ast.Name) and target.id == "_INTAKE_TIER_RE":
                call = node.value
                if isinstance(call, ast.Call) and call.args:
                    arg = call.args[0]
                    if isinstance(arg, ast.Constant):
                        pattern_str = arg.value

if pattern_str is None:
    print("ERROR: could not extract _INTAKE_TIER_RE"); sys.exit(1)

r = re.compile(pattern_str, re.MULTILINE)

valid = ["T0", "T1", "T2", "T3", "T3H", "T4", "T5", "T6"]
for tok in valid:
    m = r.search(f"tier_emitted: {tok}")
    if not m or m.group(1) != tok:
        print(f"FAIL: valid token {tok!r} not accepted"); sys.exit(1)

invalid = ["T0H", "T6H", "T3.5", "T7", "RUBBISH", "T3h", "t3h"]
for tok in invalid:
    m = r.search(f"tier_emitted: {tok}")
    if m:
        print(f"FAIL: invalid token {tok!r} accepted as {m.group(1)!r}"); sys.exit(1)

print("OK")
PYEOF
  run python3 "$py_script" "$GUARD_CLI"
  [ "$status" -eq 0 ]
  [[ "$output" == "OK" ]]
}

@test "test_entry_guard_cli_rejects_T0H_through_T6H" {
  # WHY: validates pipeline_entry_guard_cli.py:21 uses (T[0-6]|T3H) not (T[0-6]H?)
  # Write python script to temp file so bats `run` can capture exit status cleanly.
  local py_script="$TMP_DIR/check_regex.py"
  cat > "$py_script" <<'PYEOF'
import sys, re, ast

cli_path = sys.argv[1]
src = open(cli_path).read()

# WHY: parse the regex literal from source AST so test fails if the binding disappears
tree = ast.parse(src)
pattern_str = None
for node in ast.walk(tree):
    if isinstance(node, ast.Assign):
        for target in node.targets:
            if isinstance(target, ast.Name) and target.id == "_INTAKE_TIER_RE":
                call = node.value
                if isinstance(call, ast.Call):
                    arg = call.args[0]
                    if isinstance(arg, ast.Constant):
                        pattern_str = arg.value

if pattern_str is None:
    print("ERROR: could not extract _INTAKE_TIER_RE pattern")
    sys.exit(1)

r = re.compile(pattern_str, re.MULTILINE)

# Valid tokens must match and capture correctly
valid = ["T0", "T1", "T2", "T3", "T4", "T5", "T6", "T3H"]
for tok in valid:
    line = f"tier_emitted: {tok}"
    m = r.search(line)
    if not m:
        print(f"FAIL: {tok!r} should match but did not")
        sys.exit(1)
    if m.group(1) != tok:
        print(f"FAIL: {tok!r} capture group = {m.group(1)!r}, expected {tok!r}")
        sys.exit(1)

# H?-style tokens must NOT match (alternation not H? guard)
invalid = ["T0H", "T1H", "T2H", "T3H2", "T4H", "T5H", "T6H"]
for tok in invalid:
    line = f"tier_emitted: {tok}"
    m = r.search(line)
    if m:
        print(f"FAIL: {tok!r} should NOT match but captured {m.group(1)!r}")
        sys.exit(1)

print("OK")
PYEOF
  run python3 "$py_script" "$GUARD_CLI"
  [ "$status" -eq 0 ]
  [[ "$output" == "OK" ]]
}
