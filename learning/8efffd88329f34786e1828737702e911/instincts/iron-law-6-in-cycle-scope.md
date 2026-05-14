---
id: iron-law-6-in-cycle-scope
confidence: 0.5
category: pattern
domain: workflow
scope: project
project: 8efffd88329f34786e1828737702e911
roles:
  - software-engineer
  - code-reviewer
  - patch-critic
applies_to_roles:
  - software-engineer
  - code-reviewer
  - patch-critic
source: observation
created: 2026-05-14T21:53:10Z
evidence_count: 1
last_seen: 2026-05-14T21:53:10Z
---

## Pattern

When Build surfaces that a previously merged spike's "out-of-scope" test guard is now perma-freezing the files this pipeline must edit, the correct in-cycle move is to **re-scope the stale guard to its originating pipeline state directory** (so it skips when that directory is absent) — not to file a follow-up, not to delete the guard, and not to ask the user. The guard's prior load-bearing role evaporated when its source spike merged and was cleaned up; refusing to re-scope it would violate Iron Law 6 by shipping a known-incomplete fix.

## Why

Spike-leftover guards are a recurring failure mode: a defensive test written during a one-off migration spike pins specific files as "do not touch" and then survives the spike's cleanup. The next pipeline that legitimately needs to edit those files inherits a guard that fires for reasons that no longer apply. Treating the guard as immutable forces the pipeline to either skip the legitimate edit (Iron Law 6 violation — known-incomplete fix) or escalate to the user (autonomous-system violation — see [[disclosure-is-not-deferral]]).

The correct move is structural: the guard's *originating pipeline state directory* (`pipeline-state/{spike-task-id}/`) is the natural lifecycle owner. Skipping the guard when that directory is absent re-asserts the guard's original intent (protect the spike's invariants while the spike is active) and naturally retires it when the spike completes. The guard remains in tree as documentation; it just no longer fires.

## How to Apply

- **Spot the signal.** A test named `test_out_of_scope_files_untouched.py` (or similar `pinned-files` shape) fires on files this pipeline's plan names as legitimate edit targets. Cross-check: does the test reference a pipeline-state directory that no longer exists?
- **Re-scope, don't delete.** Add `if not (REPO_ROOT / "pipeline-state" / "{spike-id}").exists(): pytest.skip(...)` at the test's top. The guard stays in tree; it just becomes inert post-spike.
- **Surface the re-scope in the scratchpad** under category `iron-law-6` so the reviewer + patch-critic can validate the move was the smallest-correct fix, not a guard-deletion in disguise.
- **The reviewer's job** is to confirm (a) the spike directory is genuinely absent, (b) the re-scope preserves the guard's intent for any future re-instantiation of the spike, and (c) no other test depends on the deleted-guard's blocking behaviour.

## When NOT to Apply

- The spike is still active (pipeline-state directory exists). The guard is doing its job — find another way.
- The guard fires for a reason orthogonal to the spike's lifecycle (e.g. a security pin, a deprecated-API pin). Re-scoping to spike-directory would silently retire a guard with a different mandate.
- The pipeline's plan never intended to edit those files. The Build is over-reaching; the fix is at the plan layer, not the guard layer.

## Provenance

Pattern crystallised during `promote-advisory-hooks-enforcement` pipeline (2026-05-14). The Build surfaced that `tests/test_out_of_scope_files_untouched.py` (authored by the `harness-native-v2140-migration` spike, which merged and cleaned up its state directory) was pinning the four target hooks of this pipeline as untouchable. The in-cycle fix re-scoped the test to skip when `pipeline-state/harness-native-v2140-migration/` is absent; code-reviewer + patch-critic both APPROVED on the first round.
