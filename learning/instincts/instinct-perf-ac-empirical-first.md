---
id: instinct-perf-ac-empirical-first
confidence: 0.4
domain: performance
scope: project
project: 8efffd88329f34786e1828737702e911
roles: [architect, software-engineer, product-reviewer]
source: review-feedback
created: 2026-04-20T07:45:00Z
evidence_count: 1
last_seen: 2026-04-20T07:45:00Z
---

## Pattern
Performance acceptance criteria (latency, throughput thresholds) must either (a) include empirical profiling on target hardware BEFORE the threshold is written into the AC, or (b) be explicitly marked provisional pending first empirical run — with a documented escalation path.

## Why
A paper threshold picked without measuring the hardware floor forces either silent relaxation, bad engineering (shipping slower than stated), or mid-pipeline renegotiation. All three erode trust in the AC. An empirically-derived threshold plus safety margin is defensible; a guessed one is not.

## Evidence
- 2026-04-20 (S5.1 AC7): Plan set "median encode ≤ 15ms at 128 tokens" without profiling. Initial build measured 59.76ms — 4x over. Thread-sweep identified IntraOpThreads=8 as the single available lever (no numpy/CoreML/quantization in scope) → 15.6ms median, 0.6ms gap to target. Renegotiated to 18ms (observed median + 15% margin); documented in `ac7-renegotiation.md` with thread-sweep evidence table. Process worked, but cost a build cycle + empirical validation R1 failure.

## How to apply
- Architect: when writing a performance AC, spend 30 minutes running a smoke benchmark on target hardware first; write the AC against observed median + margin
- If benchmark is not feasible at plan time, mark the AC provisional and specify: "If empirical median > X, escalate per plan" — pre-authorize renegotiation with a rationale-required escalation path
- Product-reviewer: accept renegotiation only if (a) good-faith optimization was exhausted first (documented), (b) the new threshold is observed-median + margin, (c) business value is preserved
- Code-review: flag `sleep`-based or arbitrary-constant performance budgets as requiring empirical justification
