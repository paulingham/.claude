# runtime-state-guard: Promote-Time Hardening Gaps

> **Implementation note (2026-06-04)**: Gaps 1–5 implemented in branch fix/guard-hardening-telemetry
> (pipeline guard-hardening-telemetry-fixes, 2026-06-04).
>
> **mutation-tooling-guard.sh retired in golden-path-convergence-hooks (2026-06).** Advisory→enforcing
> soak never converged (0 telemetry across 772 sessions). The Invariant-#11 mutation-discipline path is
> superseded by the advisory `hooks/mutation-score-gate.sh` — see that hook's header for the new promotion
> criterion. The Gap 2/3 mutation-tooling-guard hardening analysis is preserved in git history at the
> pre-retirement revision.

**Created**: 2026-06-04
**Context**: guards-new-hooks batch (harden-root-contamination pipeline)
**Round**: security re-review round 2 — mandatory pre-merge condition
**Covers**: gaps that MUST be resolved before either hook flips advisory → enforcing

---

## Gap 1 — Worktree Fast-Path Lacks Registry Validation

**Status (2026-06-04): RESOLVED — see `hooks/runtime-state-guard.sh:96` (`_rsg_is_registered_worktree`) called from `_rsg_is_worktree()` line 117**

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
mkdir -p <ABS_REPO_ROOT>/$state_dir/exfil
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

## Gap 2 and Gap 3 — mutation-tooling-guard (RETIRED)

**mutation-tooling-guard.sh retired in golden-path-convergence-hooks (2026-06).** Advisory→enforcing
soak never converged (0 telemetry across 772 sessions). The Invariant-#11 mutation-discipline path is
superseded by the advisory `hooks/mutation-score-gate.sh` — see that hook's header for the new promotion
criterion. The Gap 2/3 mutation-tooling-guard hardening analysis is preserved in git history at the
pre-retirement revision.

---

## Gap 4 — runtime-state-guard Bash Coverage: cp/mv/rsync/tar

**Status (2026-06-04): RESOLVED — see `hooks/runtime-state-guard.sh:196` (`_rsg_bash_targets_pipeline_state`, renamed from `_rsg_mkdir_targets_pipeline_state`); dispatch regex extended to cp/mv/rsync at line 272**

**Severity**: LOW
**Promotion-blocking**: NO (runtime-state-guard is already enforcing; this is a coverage gap, not a bypass of existing protection)
**Files**: `hooks/runtime-state-guard.sh:136` (`_rsg_mkdir_targets_pipeline_state`), `:198` (main Bash dispatch)

### Description

The Bash-tool path only detects directory-creation invocations (via `mkdir`) when the target
is a bare path under REPO_ROOT (line 203: `if [[ "$COMMAND" =~ (^|[[:space:]])mkdir([[:space:]]|$) ]]`).
The guard fires on REPO_ROOT-relative state directories; agents must instead write to
`state_dir="${CLAUDE_PLUGIN_DATA:-${CLAUDE_CONFIG_DIR:-$HOME/.claude}}/pipeline-state"` (HARNESS_DATA).

The following commands can also create or populate `pipeline-state/` at root without
triggering the guard:

```bash
cp -r /tmp/my-state $state_dir/task           # copy in
mv /tmp/my-state $state_dir/task              # move in
rsync -a /tmp/my-state/ $state_dir/task/      # rsync in
tar -xf archive.tar pipeline-state/               # extract in
install -d $state_dir/task                    # GNU install -d (creates dirs)
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

**Status (2026-06-04): RESOLVED — escape-hatch audit record written before exit in `hooks/runtime-state-guard.sh:43-50` (writes guard-escapes.jsonl)**

**Severity**: LOW-MEDIUM
**Promotion-blocking**: NO (runtime-state-guard is already enforcing; this is a hardening item)
**Files**: `hooks/runtime-state-guard.sh:42`

### Description

This gap is called out separately as a distinct hardening item because the security re-review
explicitly flagged it.

When `CLAUDE_DISABLE_RUNTIME_STATE_GUARD=1` is set, the hook calls `exit 0` immediately with
no side-effects. There is no log entry, no metrics record, and no stderr notice. In a
post-incident investigation, there is no way to determine from the hook's own output that the
bypass was exercised.

### Proposed Fix

Add a lightweight audit write before the escape-hatch exit. The write must be best-effort
(fail-open) and must not introduce dependencies on `HARNESS_DATA` being set:

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

The log path (`guard-escapes.jsonl`) is intentionally separate from the violation log so the
two can be queried independently.

---

## Summary Table

| Gap | Severity | Promotes | Hook | Proposed Fix |
|-----|----------|----------|------|--------------|
| 1 — Worktree fast-path no registry check | MEDIUM | YES (enforcing hook bypass) | runtime-state-guard | `git worktree list` registry check |
| 2/3 — mutation-tooling-guard (RETIRED) | — | — | — | See tombstone note above |
| 4 — cp/mv/rsync/tar coverage | LOW | NO | runtime-state-guard | Extend Bash verb pattern |
| 5 — Bypass vars exit silently (no audit) | LOW-MEDIUM | NO | runtime-state-guard | Write guard-escapes.jsonl before exit |

## Promotion Checklist for runtime-state-guard (already enforcing — hardening only)

- [x] Gap 1 resolved: worktree fast-path registry check added (`_rsg_is_registered_worktree` at line 96)
- [x] Gap 4 resolved (optional, recommended): cp/mv/rsync/tar coverage (`_rsg_bash_targets_pipeline_state` at line 196; dispatch extended at line 272)
- [x] Gap 5 resolved: escape-hatch audit logging in place (`hooks/runtime-state-guard.sh:43-50`)
