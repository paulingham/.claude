---
id: harness-self-mod-probe-deferral
confidence: 0.5
category: decision
domain: hooks
scope: project
project: 8efffd88329f34786e1828737702e911
roles:
  - architect
  - infrastructure-engineer
  - software-engineer
applies_to_roles:
  - architect
  - infrastructure-engineer
  - software-engineer
source: observation
created: 2026-05-14T21:53:10Z
evidence_count: 1
last_seen: 2026-05-14T21:53:10Z
---

## Pattern

When promoting an advisory PreToolUse Agent hook to enforcement requires a schema field that may not yet be exposed by the harness (e.g. `modified_tool_input` on the Agent matcher), defer the flip behind an empirical probe artifact (`pipeline-state/{task-id}/probe-result.md`) recording the verdict (RED/GREEN) at the harness version under test. Do not flip on documentation alone — the probe is the single source of truth for "what the running harness actually accepts".

## Why

The PreToolUse Agent matcher's `modified_tool_input` field is not exposed at v2.1.141, so any hook whose semantic is *injection* (thinking defaults, advisor pairing, instinct splicing) cannot deliver its mutation through the hook layer regardless of resolver intent. Trusting docs/changelog claims that the field "should" round-trip risks shipping a hook that silently no-ops in production — the JSONL counter increments but the rendered spawn is unchanged, and the failure is invisible until a human inspects a trace.

A probe artifact (one fixture-spawn that records whether the mutation actually round-tripped) decouples the schema question from the flip decision: when the probe is RED, the hook stays advisory regardless of how clean the flip diff looks; when it flips GREEN on a later harness version, the same flip diff becomes viable without re-litigating the design.

## How to Apply

- **Before drafting a mutation-semantic hook flip plan**, check for a current probe artifact. If none exists, author one as the first slice — a single fixture that asserts the schema field round-trips end-to-end through the production hook stack.
- **Persist the probe verdict** at a known path (`pipeline-state/{task-id}/probe-result.md`) with the harness version, the test command, the literal stderr/JSONL excerpt, and a `re-probe protocol` section describing how to re-run on the next harness bump.
- **A RED probe is a hard gate.** The plan must defer the flip and ship the advisory path with a documented `CLAUDE_DISABLE_*` escape. The probe artifact becomes the trigger for the deferred flip — when it goes GREEN, the original flip diff is unblocked.
- **Do NOT use a probe to justify a flip the wrong direction.** A GREEN probe is necessary but not sufficient — the 14d soak + zero unexpected blocks gates still apply to pure-deny flips, and the operator-run JSONL review gate applies to mutation-semantic flips.

## When NOT to Apply

- Pure-deny hooks (allowlist, freshness guard, main-branch guard). These do not depend on `modified_tool_input`; the standard `exit 2 + stderr` deny idiom has always been supported on the Agent matcher.
- Non-Agent matchers (Bash, Write, Edit). These have always-supported `permissionDecision` and `exit 2` deny paths.

## Provenance

Pattern crystallised during `promote-advisory-hooks-enforcement` pipeline (2026-05-14). The plan included Slice C as a probe slice that ran the `modified_tool_input` fixture against v2.1.141 and recorded RED — confirming the v2.1.140 deferral hypothesis was still load-bearing. Three mutation-semantic hooks (`pre-agent-thinking.sh`, `pre-agent-advisor.sh`, `instinct-injector.sh`) stayed advisory; one pure-deny hook (`pre-agent-allowlist.sh`) flipped. Related: [[hook-enforcement-semantics]] — the class boundary that the probe disambiguates.
