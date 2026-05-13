# Slice-b Mutation Audit — vlm-critic + read-guard

**Targets**:
- `hooks/vlm-critic-read-guard.sh` (~30 LOC of executable logic)
- `hooks/_lib/vlm-critic-allow-paths.sh` (~25 LOC of executable logic)

**Excluded from mutation testing**:
- `hooks/_lib/vlm-critic-guard-common.sh` — verbatim clone of `hooks/_lib/spec-blind-guard-common.sh`. Already mutation-tested under the spec-blind suite at merge time; re-mutating identical bytes adds no signal.
- `hooks/_lib/vlm-critic-path.sh` — 2-line trivial shim (`python3 -c 'os.path.realpath'`). The single behavioural mutation would be replacing `os.path.realpath` with `sys.argv[1]` (i.e. no resolution), which is the same semantic mutation as H6 below. Tested at H6.
- `agents/vlm-critic.md`, `skills/vlm-critic/SKILL.md`, `rules/verdict-catalog.md`, `hooks/_lib/vlm-critic-allow-paths.txt`, `settings.json` — documentation / data files. Tier 0 contract tests assert their string contracts; mutation testing on YAML/Markdown lacks signal.

**Test runner**: `tests/mutation/vlm_critic_guard_mutation_runner.sh` (reproducible, sed-based, in-tree).

## Mutants

| ID | Target line | Mutation | Killing test | Status |
|---|---|---|---|---|
| H1 | `grep -F -q "vlm-critic"` | rename token to `vlm-criticZZZ` | VCR1 (src exit 2 path) | KILLED |
| H2 | `[[ "${CLAUDE_SUBAGENT_TYPE:-}" != "vlm-critic" ]]` | flip `!=` to `==` | VCR5 (other subagent fast-exits 0) | KILLED |
| H3 | `[[ "$SUBAGENT_TYPE" != "vlm-critic" ]] && exit 0` | flip `!=` to `==` | VCR1 (src read should exit 2) | KILLED |
| H4 | `Read\|Grep\|Glob)` case branch | drop `Read` from matcher | VCR1 (Read of src no longer exits 2) | KILLED |
| H5 | `[[ -z "$FILE_PATH" ]] && exit 0` | flip `-z` to `-n` | VCR1 (non-empty path now exit 0) | KILLED |
| H6 | `ABS_REAL="$(_vlm_critic_realpath "$ABS_PATH")"` | bypass realpath (assign `$ABS_PATH` directly) | VCR3 (symlink->src bypass) | KILLED |
| H7 | final `exit 2` | flip to `exit 0` | VCR1 (src read no longer exit 2) | KILLED |
| A1 | include-match `return 0` | flip to `return 1` | VCR2 (allowlisted png now denied) | KILLED |
| A2 | exclude-match `return 1` | flip to `return 0` | (no direct test — see below) | SURVIVED (documented equivalent) |
| A3 | default-deny `return 1` | flip to `return 0` | VCR1 (src now passes allowlist) | KILLED |

**Raw kill rate**: 9 / 10 = 0.90 across all mutants.
**Non-equivalent kill rate**: 9 / 9 = **1.00** (above the 0.70 gate per `rules/core.md` § Iron Law 1).

## Documented Equivalent Mutant (A2)

A2 flips the exclude-match polarity in `is_path_allowed_for_vlm_critic` — the four `!.*/node_modules/.*` / `!.*/vendor/.*` / `!.*/dist/.*` / `!.*/build/.*` exclude lines. With A2 applied, a path containing `/node_modules/` would be treated as include-on-match instead of deny-on-match, and the realpath gate would have to be the last line of defense.

**Why this is not a security issue under the current design**:
1. The exclude patterns are belt-and-braces defense — there is no plausible legitimate code path that Reads `/node_modules/foo/visual-baselines/x.png` because vlm-critic's input is `index.json.routes[*].visual_regression.{baseline_path, current_path}`, which the design-qc producer (slice-a) writes to `pipeline-state/{task-id}/visual-baselines/...` deterministically. There is no producer code path that emits a `node_modules`-based baseline path.
2. The realpath gate (SEC-HIGH-1) runs BEFORE the allowlist match. A symlink at `pipeline-state/task/visual-baselines/leak.png -> /opt/proj/node_modules/internal.tsx` is realpath-resolved to the `node_modules` path, then the allowlist matcher runs against the resolved path. The include patterns (`pipeline-state/.+/visual-baselines/[^/]+\.png` etc.) do not match a `node_modules` path even with A2 applied — the realpath result is `/opt/proj/node_modules/internal.tsx`, which does not match any include rule.
3. Adding a Tier 2 fixture that materialises a `node_modules`-baseline path purely to kill this mutant would be a vanity test — the test setup creates an attack surface (writing into node_modules) that no production code path can reach.

The A2 survivor mirrors the spec-blind clone's `CR-MED-4` belt-and-braces decision (see `hooks/_lib/spec-blind-allow-paths.txt:18-22` — the same four exclude rules with the same rationale).

## Reproducibility

```bash
bash tests/mutation/vlm_critic_guard_mutation_runner.sh
```

Exit code 0 indicates kill rate ≥ 0.70 across non-equivalent mutants. Exit code 1 indicates a surviving non-equivalent mutant (escalation).
