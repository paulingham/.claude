---
category: warning
---

`hooks/auto-learn-gate.sh` and `hooks/_lib/learn_status.py` are both writers to the same JSON state file (`learning/{hash}/.learn-state.json`). When you add a new field to that schema, you MUST also teach `auto-learn-gate.sh`'s `_alg_inner` to read AND re-emit it — otherwise every Stop event truncates the field, because `jq -n` builds a fresh document containing only the keys named on its command line. The Python helper's docstring used to claim "atomic read-merge-write" but that guarantee only holds against other Python callers; the bash hook is an independent writer.

---
category: pattern
---

The bats hook test pattern in `tests/test_auto_learn_gate_dual_path.py` (subprocess.run sourcing the hook from a fixed worktree path with `HOME` redirected to a tmp_path and `CLAUDE_CONFIG_DIR` pointing back at the worktree) is the working integration-test recipe for verifying hook behavior end-to-end. The trap: `HOME` alone is insufficient — the hook's first line sources `${CLAUDE_CONFIG_DIR:-$HOME/.claude}/hooks/_lib/log.sh`, so without `CLAUDE_CONFIG_DIR` the hook silently exits after a "log.sh not found" error and the test gives a false green. Always set both env vars.

---
category: discovery
---

`/learn` is a Skill, not an Agent. There is no `agents/learn-runner.md` and the historical example in `rules/_detail/reflection-protocol.md` referenced one that never shipped. The canonical dispatch is `Skill({name: "learn"})`; an Agent-tool variant is desirable in the future but is NOT a current contract — only Reflect's "must not block on completion" is.

---
category: decision
---

`learn_deferred_to_next: true` frontmatter field on pipeline state was removed (no consumer ever read it). The deferral is implicit in the `last_learn_started > last_learn_run` predicate stored in `.learn-state.json` — that file already carries the only signal the queue needs, so adding a parallel field on the per-pipeline state would have been redundant state with no audit value.
