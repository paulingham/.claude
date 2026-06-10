#!/usr/bin/env bats
# Slice C — comment-smell-check.sh (PostToolUse Write/Edit).
# BLOCKS (exit 2) on a new/changed WHAT-comment in a source file; advisory (exit 0)
# on legacy comments. Doc-comments, license headers, WHY:/SAFETY: notes, and
# directive/pragma comments always pass.
#
# MANDATORY (engineer MED-1): every block-test runs inside a real git repo created
# in setup() — git init/add/commit a temp repo and write fixtures INTO it. Without a
# git repo the new/legacy discrimination fails-open advisory and block-tests become
# FALSE GREENS. Precedent: tests/shell/codebase_map_hooks.bats:35.

setup() {
  BATS_FILE_TMPDIR="$(mktemp -d -t comment-smell.XXXXXX)"
  REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
  HOOK="$REPO_ROOT/hooks/comment-smell-check.sh"
  export CLAUDE_PLUGIN_ROOT="$REPO_ROOT"

  # A real git repo so the hook's git-based new/legacy discrimination runs for real.
  WORK="$BATS_FILE_TMPDIR/repo"
  mkdir -p "$WORK"
  cd "$WORK"
  /usr/bin/git init -q
  /usr/bin/git config user.email t@t
  /usr/bin/git config user.name t
}

teardown() { rm -rf "$BATS_FILE_TMPDIR"; }

# Helper: commit a baseline so the file is tracked, with given content.
commit_baseline() {
  local path="$1"; shift
  printf '%s' "$1" > "$WORK/$path"
  /usr/bin/git -C "$WORK" add "$path"
  /usr/bin/git -C "$WORK" commit -q -m "baseline $path"
}

run_hook() {
  local path="$1"
  run bash "$HOOK" <<EOF
{"tool_input": {"file_path": "$WORK/$path"}}
EOF
}

@test "C1: new WHAT comment above code in a tracked .rb blocks (exit 2)" {
  commit_baseline counter.rb $'class C\n  def tick\n    @n = 0\n  end\nend\n'
  printf 'class C\n  def tick\n    # increment the counter\n    @n += 1\n  end\nend\n' > "$WORK/counter.rb"
  run_hook counter.rb
  [ "$status" -eq 2 ]
  [[ "$output" == *"BLOCKED"* ]]
}

@test "C2: pre-existing WHAT comment, file edited elsewhere, is advisory (exit 0)" {
  commit_baseline counter.rb $'class C\n  def tick\n    # increment the counter\n    @n += 1\n  end\nend\n'
  # Edit a different region; the legacy comment line is unchanged.
  printf 'class C\n  def tick\n    # increment the counter\n    @n += 1\n  end\n\n  def reset\n    @n = 0\n  end\nend\n' > "$WORK/counter.rb"
  run_hook counter.rb
  [ "$status" -eq 0 ]
}

@test "C3: a new SPDX/license header line is exempt (exit 0)" {
  commit_baseline lib.rb $'class C\nend\n'
  printf '# SPDX-License-Identifier: MIT\n# Copyright 2026 Example Corp\nclass C\nend\n' > "$WORK/lib.rb"
  run_hook lib.rb
  [ "$status" -eq 0 ]
}

@test "C4: doc-comments (/** @param */, Python docstring) are exempt (exit 0)" {
  commit_baseline svc.ts $'export function f(x: number) {\n  return x\n}\n'
  printf 'export function f(x: number) {\n  /** @param x the input */\n  return x\n}\n' > "$WORK/svc.ts"
  run_hook svc.ts
  [ "$status" -eq 0 ]

  commit_baseline mod.py $'def f(x):\n    return x\n'
  printf 'def f(x):\n    """Return x unchanged."""\n    return x\n' > "$WORK/mod.py"
  run_hook mod.py
  [ "$status" -eq 0 ]
}

@test "C5: WHY:/SAFETY: prefixed comments are exempt (exit 0)" {
  commit_baseline ord.rb $'def f\n  g\nend\n'
  printf 'def f\n  # WHY: api requires this order\n  g\nend\n' > "$WORK/ord.rb"
  run_hook ord.rb
  [ "$status" -eq 0 ]

  commit_baseline ord.ts $'export function f() {\n  g()\n}\n'
  printf 'export function f() {\n  // SAFETY: must run before teardown\n  g()\n}\n' > "$WORK/ord.ts"
  run_hook ord.ts
  [ "$status" -eq 0 ]
}

@test "C6: a .md file with a WHAT comment is skipped (exit 0)" {
  commit_baseline doc.md $'# Title\n'
  printf '# Title\n<!-- increment the counter -->\n' > "$WORK/doc.md"
  run_hook doc.md
  [ "$status" -eq 0 ]
}

@test "C6: a test file with a WHAT comment is skipped (exit 0)" {
  commit_baseline thing_spec.rb $'describe X do\nend\n'
  printf 'describe X do\n  # increment the counter\n  it { is_expected.to be }\nend\n' > "$WORK/thing_spec.rb"
  run_hook thing_spec.rb
  [ "$status" -eq 0 ]
}

@test "C7: hook is wired in settings.json under Write and Edit" {
  local count
  count=$(grep -c 'hooks/comment-smell-check.sh' "$REPO_ROOT/settings.json")
  [ "$count" -ge 2 ]
}

@test "C7: hook is wired in hooks/hooks.json under Write and Edit" {
  local count
  count=$(grep -c 'hooks/comment-smell-check.sh' "$REPO_ROOT/hooks/hooks.json")
  [ "$count" -ge 2 ]
}

@test "C8: directive/pragma comments on added lines are exempt (exit 0)" {
  # frozen_string_literal magic comment
  commit_baseline app.rb $'class A\nend\n'
  printf '# frozen_string_literal: true\nclass A\nend\n' > "$WORK/app.rb"
  run_hook app.rb
  [ "$status" -eq 0 ]

  # shebang
  commit_baseline run.rb $'puts 1\n'
  printf '#!/usr/bin/env ruby\nputs 1\n' > "$WORK/run.rb"
  run_hook run.rb
  [ "$status" -eq 0 ]

  # rubocop directive
  commit_baseline lint.rb $'def f\n  g\nend\n'
  printf 'def f\n  # rubocop:disable Metrics/MethodLength\n  g\nend\n' > "$WORK/lint.rb"
  run_hook lint.rb
  [ "$status" -eq 0 ]

  # eslint-disable directive
  commit_baseline lint.ts $'export function f() {\n  g()\n}\n'
  printf 'export function f() {\n  // eslint-disable-next-line no-console\n  g()\n}\n' > "$WORK/lint.ts"
  run_hook lint.ts
  [ "$status" -eq 0 ]
}
