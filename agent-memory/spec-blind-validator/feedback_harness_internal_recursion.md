---
name: harness-internal-recursion
description: When invoked against a harness-internal pipeline (a worktree whose git-common-dir is the harness repo itself), V1 must emit SPEC_BLIND_INSUFFICIENT_SURFACE with reason harness-internal-recursion BEFORE any Read attempt
metadata:
  type: feedback
---

When the orchestrator spawns spec-blind-validator on a pipeline that modifies harness internals (skills/, agents/, hooks/, protocols/, rules/), V1 of this skill MUST emit `SPEC_BLIND_INSUFFICIENT_SURFACE` with reason `harness-internal-recursion`.

**Why:** Per `skills/spec-blind-validate/SKILL.md` § Recursion Guard, the V1 public-surface allowlist enumerates language-canonical entry points (`**/interface.{ext}`, `**/index.{ext}`, `**/__init__.py`, `**/lib.rs`, `**/*.proto`, OpenAPI/Protobuf/JSON-Schema). The harness ships none of those — it ships `hooks/*.sh`, `skills/**/SKILL.md`, `agents/*.md`, `protocols/**.md`. V2 will augment the allowlist (see § Future Work — `protocols/**.md`, `agents/*.md`, `skills/**/SKILL.md`, `orchestrator/**.md`, `CLAUDE.md`, `hooks/_lib/**.txt`) but the V2 anchor is pinned at `pipeline-state/spec-blind-validator-harness-aware-soak-end/pipeline.md` (`not_before` = 30 days post V1 merge).

**How to apply:** Detection signal — `git -C $cwd rev-parse --git-common-dir` resolves to the harness `.git` directory (e.g. `/Users/Paul.Ingham/.claude/.git`). Even if the cwd is a worktree subpath, the git-common-dir is the canonical recursion test (the SKILL.md condition 2 — realpath of toplevel — is a stricter form that doesn't catch worktrees; in practice, `git-common-dir → harness/.git` is the load-bearing signal). On detection, emit SPEC_BLIND_INSUFFICIENT_SURFACE BEFORE any Read attempt to avoid leaking harness source via the test-runner shell. The orchestrator's spawn prompt may enumerate harness paths as "public surface" but those paths are NOT yet in the V1 allowlist; surfacing the harness-aware allowlist is V2 work gated by the soak-end pipeline.

Related: [[v2-allowlist-paths]]
