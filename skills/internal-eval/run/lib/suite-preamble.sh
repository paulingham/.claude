#!/usr/bin/env bash
# Arm-strip: removes the Decision Ladder block from a harness worktree copy.
# ONLY operates on <wt-path>; never touches $HOME or the live repo.
#
# PREAMBLE global (set by suite-args.sh parse_suite_args):
#   none             → strip ladder from wt copies
#   decision-ladder  → no-op (leave wt copies byte-unchanged)
#
# Re-validate if agents/*.md are restructured: B2 catches drift.

# strip_ladder_from_harness <wt-path>
strip_ladder_from_harness() {
  local wt="$1"
  [ "$PREAMBLE" = "none" ] || return 0
  _strip_agent_ladder "$wt/agents/software-engineer.md"
  _strip_agent_ladder "$wt/agents/frontend-engineer.md"
  _strip_skill_ladder_note "$wt/skills/build-implementation/SKILL.md"
}

# WHY: deletes from the ## Decision Ladder heading (inclusive) to the line
# immediately before the next ## heading. Sed address /pattern1/,/pattern2/d
# with stop-at-but-exclude via addr,/^## /{/^## /!d} is not portable; use a
# simpler two-pass approach: mark the block then delete it via python3 which
# is already required by suite-cases-json.sh.
_strip_agent_ladder() {
  local path="$1"
  [ -f "$path" ] || return 0
  python3 - "$path" <<'PYEOF'
import sys
from pathlib import Path
p = Path(sys.argv[1])
lines = p.read_text().splitlines(keepends=True)
out = []
in_block = False
for line in lines:
    if line.rstrip() == "## Decision Ladder":
        in_block = True
        continue
    if in_block and line.startswith("## "):
        in_block = False
    if not in_block:
        out.append(line)
p.write_text("".join(out))
PYEOF
}

# WHY: the SKILL.md note is a single paragraph on one logical line — no heading
# boundary. Identify it by its unique sentinel phrase and delete that paragraph.
_strip_skill_ladder_note() {
  local path="$1"
  [ -f "$path" ] || return 0
  python3 - "$path" <<'PYEOF'
import sys
from pathlib import Path
SENTINEL = "Decision Ladder (ADVISORY"
p = Path(sys.argv[1])
lines = p.read_text().splitlines(keepends=True)
out = [ln for ln in lines if SENTINEL not in ln]
p.write_text("".join(out))
PYEOF
}
