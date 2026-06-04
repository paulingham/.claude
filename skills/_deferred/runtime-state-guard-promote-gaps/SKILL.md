# runtime-state-guard + mutation-tooling-guard: Promote-Time Hardening Gaps

**Created**: 2026-06-04
**Context**: guards-new-hooks batch (harden-root-contamination pipeline)
**Round**: security re-review round 2 — mandatory pre-merge condition
**Covers**: gaps that MUST be resolved before either hook flips advisory → enforcing

---

## Gap 1 — Worktree Fast-Path Lacks Registry Validation

**Severity**: MEDIUM
**Promotion-blocking**: YES (runtime-state-guard.sh is already enforcing; this gap admits a bypass)
**Files**: `hooks/runtime-state-guard.sh:80` (`_rsg_is_worktree()` fast-path)

### Description

`_rsg_is_worktree()` contains a fast-path that allows any CWD whose canonicalized
path matches `*/.claude/worktrees/agent-*` without checking whether that path is a
git-registered worktree for the current REPO_ROOT.

```bash
# runtime-state-guard.sh:80 — fast-path (no registry check)
[[ "$canon_pwd" == *"/.claude/worktrees/agent-"* ]] && return 0
```

### Exploit

An agent (or a compromised session) can create a directory that matches the pattern,
`cd` into it, and then issue an absolute-path `mkdir` targeting REPO_ROOT/pipeline-state:

```bash
mkdir -p .claude/worktrees/agent-evil
cd .claude/worktrees/agent-evil
mkdir -p <ABS_REPO_ROOT>/pipeline-state/exfil
# → _rsg_is_worktree() returns 0 (fast-path matches) → guard exits 0 → ALLOWED
```

The guard is bypassed because it trusts the directory name pattern without verifying
the path is registered via `git worktree list`.

### Proposed Fix

Two options (choose one):

**Option A — Registry check** (preferred, mirrors `_mbd_target_is_valid_worktree`
pattern in `hooks/main-branch-guard.sh`):

```bash
_rsg_is_registered_worktree() {
    local path="$1"
    git worktree list --porcelain 2>/dev/null \
        | awk '/^worktree /{print $2}' \
        | while IFS= read -r wt; do
            local canon_wt
            canon_wt=$(cd "$wt" 2>/dev/null && pwd -P) || continue
            [[ "$path" == "$canon_wt" || "$path" == "$canon_wt/"* ]] && return 0
          done
}
```

Then replace the fast-path with: `_rsg_is_registered_worktree "$canon_pwd" && return 0`

**Option B — Restrict fast-path scope**: Only apply the pattern-match fast-path when
`canon_pwd` is a REPO_ROOT-relative subpath (i.e. starts with `$REPO_ROOT/`), and
separately block any absolute-path mkdir targets from a CWD that merely looks like a
worktree pattern. This is weaker than Option A.

---

## Gap 2 — mutation-tooling-guard Regex Obfuscation Bypasses

**Severity**: MEDIUM
**Promotion-blocking**: YES (advisory → enforcing flip requires zero confirmed bypass paths)
**Files**: `hooks/mutation-tooling-guard.sh:77` (`_mtg_is_mutmut`), `:83` (`_mtg_is_sed_inplace_source`)

### Description

The pattern detectors match on literal command strings. Several trivial obfuscations
bypass all three detectors:

| Bypass | Example | Why it works |
|--------|---------|--------------|
| Backslash escape | `s\ed -i 's/x/y/' src.py` | `sed` regex does not match `s\ed` |
| Command substitution | `$(echo mutmut) run` | mutmut regex does not match the substitution form |
| `bash -c` wrapper | `bash -c 'sed -i ...'` | outer command is `bash`, not `sed` |
| Python module | `python -m mutmut run` | mutmut regex only matches bare `mutmut` |
| `eval` wrapper | `eval "sed -i 's/x/y/' src.py"` | outer command is `eval` |

### Proposed Fix

Before pattern matching, normalize the command string:
1. Resolve simple `$(echo X)` substitutions via a conservative regex strip.
2. Recurse into `bash -c '...'` argument strings (extract and re-test the inner command).
3. Add `python -m mutmut` as an explicit pattern in `_mtg_is_mutmut`.
4. Add `eval "sed ..."` detection (flag any eval containing a source-extension target).

Backslash-escaped commands (`s\ed`) are unlikely in practice but can be handled by
normalizing `\` + identifier sequences before matching.

---

## Gap 3 — Env-Var Bypass: Guard Variables and Context Variables

**Severity**: MEDIUM
**Promotion-blocking**: YES for mutation-tooling-guard; LOW for runtime-state-guard (enforcing; gap narrower)
**Files**: `hooks/mutation-tooling-guard.sh:42`, `:52`; `hooks/runtime-state-guard.sh:42`

### Description

**Bypass A — Escape-hatch vars**: Both hooks short-circuit silently on their disable
env vars:

```bash
# mutation-tooling-guard.sh:42
[[ "${CLAUDE_DISABLE_MUTATION_TOOLING_GUARD:-0}" == "1" ]] && exit 0

# runtime-state-guard.sh:42
[[ "${CLAUDE_DISABLE_RUNTIME_STATE_GUARD:-0}" == "1" ]] && exit 0
```

These are intentional escapes (per protocol), but they write no audit record. A
session that sets the var and then contaminates root is invisible to post-incident
forensics.

**Bypass B — Context-var clearing**: mutation-tooling-guard only fires when
`CLAUDE_WORKTREE_PATH` is set (line 52: `[[ -n "${CLAUDE_WORKTREE_PATH:-}" ]] || exit 0`).
A session can unset or clear this variable before invoking mutation tooling, bypassing
the entire guard:

```bash
unset CLAUDE_WORKTREE_PATH
mutmut run   # → guard exits 0 (no worktree context declared)
```

Similarly, clearing `HOME`, `CLAUDE_CONFIG_DIR`, or `CLAUDE_PLUGIN_ROOT` before running
the hook can affect `HARNESS_DATA` resolution and the advisory log path.

### Proposed Fix

**Bypass A**: Before the escape-hatch `exit 0`, write an audit JSONL record to a
well-known path (e.g. `$HARNESS_DATA/metrics/${session}/guard-escapes.jsonl`) so
forensics can identify sessions that bypassed guards. Example:

```bash
if [[ "${CLAUDE_DISABLE_RUNTIME_STATE_GUARD:-0}" == "1" ]]; then
    _rsg_log_escape  # writes {timestamp, session_id, guard, action:"escaped"} to JSONL
    exit 0
fi
```

**Bypass B**: Add a secondary signal — if `CLAUDE_WORKTREE_PATH` is unset but
`REPO_ROOT` itself is NOT a worktree path, and a mutation command is detected,
emit a reduced-confidence advisory (noting that worktree context could not be
verified). This requires a heuristic (e.g. check `git worktree list` output for
any active worktrees) rather than relying solely on the env var.

---

## Gap 4 — runtime-state-guard Bash Coverage: cp/mv/rsync/tar

**Severity**: LOW
**Promotion-blocking**: NO (runtime-state-guard is already enforcing; this is a coverage gap, not a bypass of existing protection)
**Files**: `hooks/runtime-state-guard.sh:136` (`_rsg_mkdir_targets_pipeline_state`), `:198` (main Bash dispatch)

### Description

The Bash-tool path only detects `mkdir` invocations targeting `pipeline-state/`
under REPO_ROOT (line 203: `if [[ "$COMMAND" =~ (^|[[:space:]])mkdir([[:space:]]|$) ]]`).

The following commands can also create or populate `pipeline-state/` at root without
triggering the guard:

```bash
cp -r /tmp/my-state pipeline-state/task           # copy in
mv /tmp/my-state pipeline-state/task              # move in
rsync -a /tmp/my-state/ pipeline-state/task/      # rsync in
tar -xf archive.tar pipeline-state/               # extract in
install -d pipeline-state/task                    # GNU install -d (creates dirs)
```

### Proposed Fix

Extend the Bash-tool check to cover `cp`, `mv`, `rsync`, and `tar -x` when the
destination or extraction path resolves under `REPO_ROOT/pipeline-state/`.

Pattern additions to `_rsg_mkdir_targets_pipeline_state` (rename to
`_rsg_bash_targets_pipeline_state`):

```bash
# cp/mv: last non-flag argument is destination — requires simple word scanning
# rsync: destination is last word (same pattern)
# tar -x: check for -C flag followed by pipeline-state path, or extraction member names
```

Note: full coverage requires parsing destination-argument position, which is more
complex than detecting mkdir. A conservative heuristic (flag any command containing
both a write verb and a `pipeline-state` path token) reduces false-negative exposure.

---

## Gap 5 — Bypass Env-Vars Exit Silently (No Audit Record)

**Severity**: LOW-MEDIUM
**Promotion-blocking**: YES for advisory → enforcing promotion of mutation-tooling-guard (audit trail required)
**Files**: `hooks/mutation-tooling-guard.sh:42`; `hooks/runtime-state-guard.sh:42`

### Description

This gap is related to Gap 3 Bypass A but is called out separately as a distinct
promotion-blocking item because the security re-review explicitly flagged it.

When `CLAUDE_DISABLE_RUNTIME_STATE_GUARD=1` or `CLAUDE_DISABLE_MUTATION_TOOLING_GUARD=1`
is set, both hooks call `exit 0` immediately with no side-effects. There is no log
entry, no metrics record, and no stderr notice. In a post-incident investigation,
there is no way to determine from the hook's own output that the bypass was exercised.

This is acceptable during early soak (advisory mode), but becomes a forensics gap
once either hook is enforcing or is promoted to enforcing.

### Proposed Fix

Add a lightweight audit write before each escape-hatch exit. The write must be
best-effort (fail-open) and must not introduce dependencies on `HARNESS_DATA` being
set (since the escape may be exercised in contexts where path resolution is broken):

```bash
# Example: runtime-state-guard.sh
if [[ "${CLAUDE_DISABLE_RUNTIME_STATE_GUARD:-0}" == "1" ]]; then
    local _sid="${CLAUDE_SESSION_ID:-local-$$}"; _sid="${_sid//[^a-zA-Z0-9_.-]/}"
    local _dir="${HARNESS_DATA:-$HOME/.claude}/metrics/${_sid}"
    mkdir -p "$_dir" 2>/dev/null && \
        printf '{"timestamp":"%s","session_id":"%s","guard":"runtime-state-guard","action":"escaped"}\n' \
            "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$_sid" \
            >> "$_dir/guard-escapes.jsonl" 2>/dev/null || true
    exit 0
fi
```

Same pattern for mutation-tooling-guard. The log path (`guard-escapes.jsonl`) is
intentionally separate from the violation log so the two can be queried independently.

---

## Summary Table

| Gap | Severity | Promotes | Hook | Proposed Fix |
|-----|----------|----------|------|--------------|
| 1 — Worktree fast-path no registry check | MEDIUM | YES (enforcing hook bypass) | runtime-state-guard | `git worktree list` registry check |
| 2 — Regex obfuscation bypasses | MEDIUM | YES (advisory flip blocked) | mutation-tooling-guard | Normalize + recurse into bash -c / python -m |
| 3 — Env-var bypass (CLAUDE_WORKTREE_PATH unset / HOME cleared) | MEDIUM | YES (advisory flip blocked) | mutation-tooling-guard | Heuristic fallback + secondary worktree detection |
| 4 — cp/mv/rsync/tar coverage | LOW | NO | runtime-state-guard | Extend Bash verb pattern |
| 5 — Bypass vars exit silently (no audit) | LOW-MEDIUM | YES (forensics requirement) | both | Write guard-escapes.jsonl before exit |

## Promotion Checklist for mutation-tooling-guard

Before flipping `exit 0` → `exit 2` at `hooks/mutation-tooling-guard.sh:171`:

- [ ] Gap 2 resolved: obfuscation bypasses addressed
- [ ] Gap 3 resolved: CLAUDE_WORKTREE_PATH-unset bypass addressed
- [ ] Gap 5 resolved: escape-hatch audit logging in place
- [ ] N=10 distinct sessions with advisory events, zero confirmed false-positive blocks
      (`jq -r '.session_id' "$HARNESS_DATA"/metrics/*/mutation-tooling-advisory.jsonl | sort -u | wc -l`)

## Promotion Checklist for runtime-state-guard (already enforcing — hardening only)

- [ ] Gap 1 resolved: worktree fast-path registry check added
- [ ] Gap 4 resolved (optional, recommended): cp/mv/rsync/tar coverage
- [ ] Gap 5 resolved: escape-hatch audit logging in place
