---
id: instinct-subprocess-timeout-expired
confidence: 0.6
category: pattern
domain: code-style
scope: project
project: 8efffd88329f34786e1828737702e911
roles: [software-engineer, code-reviewer, security-engineer]
applies_to_roles: [software-engineer, code-reviewer, security-engineer]
source: review-feedback
created: 2026-04-20T13:45:00Z
evidence_count: 2
last_seen: 2026-04-28T11:09:50Z
---

## Pattern
Every `subprocess.run(..., timeout=N)` call MUST be wrapped in `try/except subprocess.TimeoutExpired` (narrow catch, not bare `Exception`). Same rule applies to argv parsing in scripts: catch only the specific exception you expect (IndexError, ValueError) — never bare `Exception` or `except:`.

## Why
A stalled subprocess (network-hung brew, HuggingFace download, slow shell script) raises `subprocess.TimeoutExpired` that escapes through any calling function unless explicitly caught. When the caller's contract is "never raise" (e.g., a bootstrap `run()` that must degrade gracefully), an uncaught timeout silently violates the invariant and crashes the surrounding flow. The existing failure-path helper (for non-zero returncode) does NOT cover this case because the process never completed.

## Evidence
- 2026-04-20 (S9 AC9-timeout-gap): `bootstrap_steps.install_ort()` (brew install, 300s timeout) and `download_model()` (HF download, 600s timeout) both set `timeout=N` without catching `TimeoutExpired`. Build-engineer wrote the timeout; code-reviewer did not flag the missing handler; security-engineer caught it in round-2 review as a DoS/correctness concern. Fix: extracted `_run_timed(cmd, warn_msg, timeout, env=None)` helper with narrow `except subprocess.TimeoutExpired` returning the same partial code as non-zero returncode. Three tests added (RED→GREEN) before merge. AC9 "run() never raises" invariant restored.
- Three-way miss: test for non-zero returncode existed, but no test exercised the TimeoutExpired path. TDD gap — behavior was plausibly correct but unexercised.
- 2026-04-28 (wave4-O scratchpad): same family — argv parsing in `auto-learn-gate.sh` helper used overly-broad exception catches. Decision recorded as "narrow except clauses (IndexError/ValueError only for argv)". Pattern generalises beyond subprocess: any narrow-catch call site needs the specific exception, never bare `Exception`.

## How to apply
- Build: grep for `subprocess.run.*timeout=` before completing any module — every match must have a sibling `except subprocess.TimeoutExpired` (direct or via a helper).
- Build: if two+ call sites share the timeout-handling shape, extract a `_run_timed` helper (2nd-occurrence DRY).
- Code-review: when reviewing any file containing `subprocess.run(..., timeout=...)`, verify the TimeoutExpired path has a test. If the test is missing, it's CHANGES_REQUESTED even if the code looks correct.
- QA/verify: mutation test the timeout path — add a test that simulates `TimeoutExpired` and asserts the caller's contract is honored (returns code, logs warn, doesn't raise).
- Never use bare `except:` or `except Exception:` — always `except subprocess.TimeoutExpired` (plus separate handlers for `FileNotFoundError`, `PermissionError` if those are real concerns).
