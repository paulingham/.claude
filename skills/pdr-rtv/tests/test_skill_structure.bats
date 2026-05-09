#!/usr/bin/env bats
# AC1 — `~/.claude/skills/pdr-rtv/SKILL.md` exists with valid YAML frontmatter
# (`name`, `description`, `verdict`, `phase: build`, `dispatch: team`); the
# description references the User-Intent Reconciliation paragraph; canonical-
# template audit (mirrored from Best-of-N) exits 0.

setup() {
  REPO_ROOT="$(cd "${BATS_TEST_DIRNAME}/../../.." && pwd)"
  SKILL_PATH="$REPO_ROOT/skills/pdr-rtv/SKILL.md"
  AUDIT_SCRIPT="$REPO_ROOT/scripts/test_pdr_rtv_skill_structure.sh"
}

@test "AC1: skill_md_has_canonical_frontmatter" {
  [ -f "$SKILL_PATH" ]

  # Frontmatter delimited by --- on line 1 and a later ---.
  first_line="$(sed -n '1p' "$SKILL_PATH")"
  [ "$first_line" = "---" ]
  fm_close="$(awk 'NR>1 && /^---$/ {print NR; exit}' "$SKILL_PATH")"
  [ -n "$fm_close" ]

  fm_block="$(sed -n "2,$((fm_close - 1))p" "$SKILL_PATH")"
  for field in name description verdict phase dispatch; do
    grep -Eq "^${field}:[[:space:]]" <<<"$fm_block"
  done

  # phase: build, dispatch: team (exact values).
  grep -Eq '^phase:[[:space:]]*build[[:space:]]*$' <<<"$fm_block"
  grep -Eq '^dispatch:[[:space:]]*team[[:space:]]*$' <<<"$fm_block"

  # Description references User-Intent Reconciliation (case-insensitive).
  grep -Eqi 'user.intent reconciliation' <<<"$fm_block"
}

@test "AC1: canonical_template_audit_exits_zero" {
  [ -x "$AUDIT_SCRIPT" ]
  run "$AUDIT_SCRIPT"
  [ "$status" -eq 0 ]
  [[ "$output" == *"STRUCTURE_OK"* ]]
}
