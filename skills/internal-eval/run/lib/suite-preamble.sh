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
# immediately before the next ## heading. If the ladder is the last ## section,
# the block is bounded by the carve-out sentinel (NEVER simplified away) plus
# its item list: once we see a blank line after the last carve-out item, we
# stop deleting — protecting any non-heading trailing content that follows.
_strip_agent_ladder() {
  local path="$1"
  [ -f "$path" ] || return 0
  python3 - "$path" <<'PYEOF'
import sys
from pathlib import Path
CARVE_OUT = "NEVER simplified away"
p = Path(sys.argv[1])
lines = p.read_text().splitlines(keepends=True)
out = []
in_block = False
past_carve_out = False
carve_out_items_seen = 0
for line in lines:
    if line.rstrip() == "## Decision Ladder":
        in_block = True
        continue
    if in_block and line.startswith("## "):
        in_block = False
    if in_block and CARVE_OUT in line:
        past_carve_out = True
    if in_block and past_carve_out and line.startswith("- "):
        carve_out_items_seen += 1
    if in_block and past_carve_out and carve_out_items_seen > 0 and line.strip() == "":
        in_block = False
        out.append(line)
        continue
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
