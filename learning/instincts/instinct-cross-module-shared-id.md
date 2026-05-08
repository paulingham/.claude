---
id: instinct-cross-module-shared-id
confidence: 0.6
domain: testing
scope: project
project: 8efffd88329f34786e1828737702e911
roles: [software-engineer, code-reviewer, qa-engineer]
source: review-feedback
created: 2026-04-20T07:45:00Z
evidence_count: 2
last_seen: 2026-04-20T13:45:00Z
---

## Pattern
When two modules share an identifier (hash, id, key, reference token), always require a full-path integration test that uses that identifier end-to-end — module-local unit tests are insufficient for cross-module contracts.

## Why
Unit tests pass when each module is shape-compliant in isolation. But a width/format mismatch across the boundary (e.g., 16-char prefix vs 64-char full hash) produces a silent no-op that no local test can detect. Only a test that exercises `moduleA → shared_id → moduleB` catches it.

## Evidence
- 2026-04-20 (S5.1 D2): `search_tier` projected a 16-char prefix as `content_hash`; `vec_store.load` queried the `embeddings` table expecting 64-char full hashes. Both modules unit-tested and shape-compliant. Rerank silently returned cosine=0 for every candidate — the entire blend was a no-op in production since S5 shipped. Survived build self-review, 2 rounds of code review, security review, and verify mutation testing. Caught only by `test_recall_rerank_full_path.py` written post-hoc as a regression guard.
- 2026-04-20 (S9 AC11): bootstrap writes `ORT_DYLIB_PATH` to `settings.json`; `paths.resolve_dylib()` reads it from `os.environ`. The shared identifier is the env var name + the path format. `test_bootstrap_integration.py::BootstrapToPathsIntegration` was planned upfront as an AC, not discovered post-hoc — the S5.1 lesson prevented a repeat. Pattern applied proactively.

## How to apply
- During build/review: when a new identifier crosses a module boundary, require a test that inserts data via one path and reads it via the other using that identifier
- Code-review checklist: flag shared-identifier cross-module flow as requiring a full-path test
- Naming rule: if a field is `content_hash` in one module and `content_hash` in another, assume nothing about format — verify with a test that uses them together
