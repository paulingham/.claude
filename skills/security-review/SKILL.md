---
name: "security-review"
description: "Use when user wants to Security Review phase skill: spawn security-engineer agent for OWASP Top 10 audit, dependency scanning, secrets detection, and auth/authz review. Runs after Build (which now includes code-review as its final step) and gates Final Gate."
context: fork
agent: security-engineer
---

# Security Review

## § 0 — SAST Triage Layer (Pre-Rubric)

> **Runs BEFORE the OWASP rubric below.** Triage is purely additive: it ingests
> SAST output (Semgrep, CodeQL, others producing SARIF), assigns each finding
> a `keep | drop | unsure` verdict with mandatory rationale, merges
> `keep`+`unsure` into the agent's working set, and logs every decision to a
> forensic JSONL stream. The OWASP rubric is unchanged and runs INDEPENDENTLY
> alongside the triage block.

### § 0 — Bypass switch

When `CLAUDE_DISABLE_SAST_TRIAGE=1`, § 0 exits early with `TRIAGE_BYPASSED`
BEFORE detection (rung 1 is never inspected). The main `metrics/$SESSION/sast-triage.jsonl`
is NOT touched. A single bypass record is written to a DISTINCT ledger
`metrics/$SESSION/sast-triage-bypass.jsonl` (verdict: `BYPASSED`,
reason: `CLAUDE_DISABLE_SAST_TRIAGE=1`). Stderr emits
`SAST triage bypassed via CLAUDE_DISABLE_SAST_TRIAGE`. OWASP rubric proceeds
unchanged.

### § 0.1 — Detection ladder (4 rungs, first hit wins)

| Rung | Source | When |
|---|---|---|
| rung 1 | `$CLAUDE_SAST_SARIF_PATH` (operator override) | CI providing pre-computed SARIF |
| rung 2 | `$state_dir/{task_id}/scratchpad/sast-*.sarif` | Earlier pipeline phase staged SARIF |
| rung 3 | direct semgrep subprocess (`semgrep --sarif --json --quiet -- <changed>`) on `git diff main...HEAD` files | On-demand fallback when rungs 1-2 absent. Bounded by `CLAUDE_SAST_SEMGREP_TIMEOUT_SEC` (default 60s). `shutil.which("semgrep") is None` → rung skipped silently. |
| rung 4 | None | Tool not installed and no staged SARIF — emit `TRIAGE_NO_INPUT`, OWASP rubric proceeds |

If any rung resolves to a file/source but parsing fails (corrupt JSON, SARIF
shape error, semgrep crash), the runner logs the rung that fired plus the
parse error class (`json-decode-error | sarif-shape-error | semgrep-shape-error
| subprocess-failed`) and falls through. If ALL rungs that resolved produced
parse failures, § 0 emits `TRIAGE_PARSE_FAILED` (DISTINCT from
`TRIAGE_NO_INPUT`) and OWASP rubric proceeds.

### § 0.2 — Parsing & severity normalization

Findings filtered to changed-files-only at parse time (NOT triaged, NOT logged
for unchanged files).

| Tool | Raw | Normalized |
|---|---|---|
| Semgrep | `ERROR` | `CRITICAL` |
| Semgrep | `WARNING` | `HIGH` |
| Semgrep | `INFO` | `LOW` |
| SARIF (CodeQL etc.) | `error` | `HIGH` |
| SARIF | `warning` | `MEDIUM` |
| SARIF | `note` | `LOW` |
| SARIF | `none` | `INFO` |

Unknown severities → `INFO` + stderr warning.

### § 0.3 — Triage iteration (the agent runs this loop)

> **The security-engineer agent IS the LLM caller.** This section contains the
> iteration template the agent executes inline — `for each finding`,
> render the prompt below, parse the strict-JSON response, validate it via
> `hooks/_lib/sast_triage.py::triage_finding(parsed)`, and append
> the result to the merged working set.

For each finding produced by § 0.2, render this prompt and call the model
once (per-finding for v1; batching is a v2 follow-up):

```
You are triaging a SAST finding for inclusion in a security review.

Finding:
  Tool: {tool}
  Rule: {rule_id}
  Severity: {sast_severity}
  File: {file}:{line}
  Message: {message}
  Code:
    {snippet}

Decision rules:
- keep:   This is a real vulnerability or potential vulnerability.
- drop:   This is a confirmed false positive. Provide a 1–2 sentence rationale.
- unsure: You cannot determine with confidence. Default here when in doubt.

Output (strict JSON, no prose):
{
  "verdict": "keep" | "drop" | "unsure",
  "rationale": "1–2 sentence explanation. MUST NOT be empty. MUST NOT be 'N/A' or similar."
}

Conservatism rule: When in doubt, choose `unsure`. A wrong `drop` ships a vulnerability.
```

Strict-JSON output contract: `verdict ∈ {keep, drop, unsure}`. Rationale must
be non-empty, non-`N/A`, ≥ 8 tokens, and not in the parser's stop-list. The
parser force-rewrites bad outputs to `unsure` with a system rationale.

### § 0.4 — Merge into working set

`keep` + `unsure` findings render into a `## SAST Triage Findings (Pre-Rubric)`
block PREPENDED to the agent's review. `drop` findings are excluded from the
merge block but ARE recorded in the JSONL ledger.

```markdown
## SAST Triage Findings (Pre-Rubric)

### keep (N findings)
- **{rule_id}** `{file}:{line}` (sast={sast_severity}) — {message}
  - Triage rationale: {rationale}

### unsure (M findings)
- **{rule_id}** `{file}:{line}` (sast={sast_severity}) — {message}
  - Triage uncertainty: {rationale}
```

### § 0.5 — Telemetry JSONL

Every triage decision (incl. `drop`) appends one record to
`metrics/$SESSION/sast-triage.jsonl`:

| field | description |
|---|---|
| `ts` | unix seconds |
| `session_id` | `$CLAUDE_SESSION_ID` |
| `task_id` | pipeline task-id |
| `rule_id` | tool rule identifier |
| `tool` | `semgrep` / `codeql` / `other` |
| `file` | changed file path |
| `line` | line number |
| `sast_severity` | normalized severity |
| `verdict` | `keep` / `drop` / `unsure` |
| `rationale_excerpt` | first 200 chars of rationale, single-line |
| `rationale_full_hash` | `sha1:` + sha1 of full rationale |

Telemetry write failure logs to stderr but does NOT block triage.

### § 0.6 — Operator-surface env vars

| Env var | Effect |
|---|---|
| `CLAUDE_DISABLE_SAST_TRIAGE=1` | Skip § 0 entirely; write one record to bypass ledger |
| `CLAUDE_SAST_SARIF_PATH` | Pre-staged SARIF — operator override; rung 1 wins |
| `CLAUDE_SAST_SEMGREP_TIMEOUT_SEC` | Override 60s default for rung-3 subprocess |

---

## Advisor Mode (Sonnet executor + Opus advisor)

**Pairing**: security-engineer ships with `executor: claude-sonnet-4-6` and `advisor: claude-opus-4-7` in its frontmatter. Sonnet drives the OWASP/secrets sweep, Opus is consulted for threat-model and severity-classification calls.

**Status**: This is the **intended default** — currently advisory because the Agent input schema does not yet expose `advisor`. Will become the enforced default the moment the schema lands. Until then, the `pre-agent-advisor.sh` PreToolUse hook logs the would-be pairing to `metrics/{session}/advisor-dispatch.jsonl` for observability; no spawn is blocked, no model is downgraded.

**Fallback semantics** (all log-only today, all enforced later):
- Frontmatter pairing present + `ANTHROPIC_API_KEY` set + `CLAUDE_REVIEW_ADVISOR_DISABLED` unset → executor=sonnet, advisor=opus (`source: frontmatter-pairing`)
- `CLAUDE_REVIEW_ADVISOR_DISABLED=1` → executor/advisor both null, `source: env-disabled` (operator override; pure `model:` opus solo)
- `ANTHROPIC_API_KEY` missing → executor/advisor both null, `source: no-api-key`
- Frontmatter omits executor/advisor (non-reviewer agents) → `source: no-pairing-frontmatter`

**Cost** (PROVISIONAL pending advisor-baseline):
- Naive Opus-solo cost vs. Sonnet+Opus-advisor pairing: roughly ~40% cheaper per review (PROVISIONAL — see `eval/baselines/{latest}-advisor-baseline.md`).
- Quality-equivalence claim (≥95% verdict-agreement on the regression suite) is also PROVISIONAL until advisor-baseline runs.

## What This Skill Does

Automates the Review phase security audit. Spawns a read-only security-engineer agent to assess security posture.

## Current Context
- Branch: !`git branch --show-current`
- Changed files: !`git diff main...HEAD --name-only 2>/dev/null || echo 'N/A'`
- Diff stats: !`git diff main...HEAD --stat 2>/dev/null || echo 'N/A'`

## When to Invoke

- After Build phase emits `BUILD_COMPLETE` (which now includes code-reviewer APPROVE as a step inside Build).
- Runs as its own phase — code-review is no longer parallel with security-review because code-review is now part of Build. Security review's gate is independent.
- APPROVE required before advancing to Final Gate (verify + test + accept + patch-critique).

## Process

### 1. Spawn Security Engineer

```
// Spawn in same message as code-reviewer for parallel execution
Agent({
  subagent_type: "security-engineer",
  prompt: "Security review of changes on this branch against main. Assess:
    - OWASP Top 10 vulnerabilities (injection, XSS, CSRF, etc.)
    - Authentication and authorization (are auth checks present and correct?)
    - Input validation at system boundaries
    - Secrets in code or commits (API keys, tokens, passwords)
    - Dependency vulnerabilities (run npm audit / bundle audit)
    - Secure cookie flags, HTTPS enforcement
    - Content-Type validation on file uploads
    - If the diff touches learning/, agent-memory/, or hooks/, ALSO apply the Agentic OWASP Top 10 checklist (memory poisoning, instinct poisoning, tool misuse, goal hijacking) — see agents/security-engineer.md § OWASP Top 10 for Agentic Applications.
    Produce a verdict with severity levels: CRITICAL, HIGH, MEDIUM, LOW.
    APPROVE if no CRITICAL, HIGH, or MEDIUM findings. CHANGES_REQUESTED if any CRITICAL, HIGH, or MEDIUM findings exist. LOW and INFO findings are noted in the review output but do not block."
})
```

No `isolation: "worktree"` — security-engineer is read-only.

### 2. Process Verdict

- **APPROVE** (no CRITICAL/HIGH/MEDIUM): Advance. Record security summary for PR narrative.
- **CHANGES_REQUESTED**: Spawn engineer (with worktree) to fix CRITICAL/HIGH/MEDIUM findings. Then re-run both reviews.

## Security Checklist

- [ ] No SQL/NoSQL injection vectors
- [ ] No XSS vulnerabilities (output encoding, CSP)
- [ ] No hardcoded secrets or credentials
- [ ] Auth checks on all protected routes/endpoints
- [ ] Input validation on external boundaries
- [ ] Dependencies free of known CVEs (`npm audit` / `bundle audit`)
- [ ] Secure cookie flags (HttpOnly, Secure, SameSite)
- [ ] No sensitive data in logs or error messages
- [ ] HTTPS enforced for all external communication
- [ ] File upload validation (type, size, content)

## Agentic Surface Gate

Changes touching the agent control plane — `learning/`, `agent-memory/`, or
`hooks/` — require the **Agentic OWASP Top 10** checklist (memory poisoning,
instinct poisoning, tool misuse, goal hijacking; see
`agents/security-engineer.md` § OWASP Top 10 for Agentic Applications).

**Enforcement.** The `agentic-security-gate.sh` PreToolUse:Agent hook computes
the branch changeset and, when any agentic surface is touched, **blocks**
(`exit 2`) the security-engineer spawn unless the spawn prompt carries the
Agentic OWASP directive. The §1 spawn prompt above always carries it, so
skill-driven reviews pass; the gate catches ad-hoc spawns that omit it.

| Env var | Effect |
|---|---|
| `CLAUDE_DISABLE_AGENTIC_GATE=1` | Skip the gate; the spawn proceeds (logged to stderr) |

Gating-trigger logic lives in `hooks/_lib/agentic_security_gate.py`
(`touches_agentic_surface` / `gate_decision`); tests in
`tests/hooks/test_agentic_security_gate.py`.

## Supply Chain Security (if Trail of Bits plugins available)

When Trail of Bits security skills are installed (`supply-chain-risk-auditor`, `variant-analysis`, `differential-review`):

- [ ] Run `supply-chain-risk-auditor` on new/updated dependencies (typosquatting, maintainer compromise, post-install scripts)
- [ ] If a vulnerability is found, run `variant-analysis` to find similar patterns across the codebase
- [ ] Use `differential-review` for security-focused diff analysis on high-risk changes

These complement `npm audit`/`bundle audit` by covering supply chain threats that package auditors miss.

## Parallel Execution

This skill belongs to the `review` parallel group. It is dispatched via Parallel Dispatch Protocol (see `protocols/parallel-dispatch-protocol.md`), not via sequential Skill tool invocation. The security-engineer agent reads this file directly and executes it.

When dispatched in parallel:
1. The orchestrator spawns code-reviewer + security-engineer in a single message
2. Each agent reads its own skill file independently
3. The orchestrator collects both verdicts before proceeding

## Prerequisite

- Build phase complete: BUILD_COMPLETE verdict from `/harness:build-implementation`, `/harness:refactor`, or `/harness:bug-fix`
- Must be dispatched IN PARALLEL with `/harness:code-review` via Parallel Dispatch Protocol

## Severity Grading

Every finding MUST be assigned a severity. Use the calibration table below:

| Severity | Definition | Examples | Blocks? |
|----------|-----------|----------|---------|
| CRITICAL | Security vulnerability or data loss risk | SQL injection, exposed secrets, auth bypass | Yes |
| HIGH | Correctness bug or significant design flaw | Missing error handling, broken invariant, SOLID violation | Yes |
| MEDIUM | Code quality issue causing maintenance pain | DRY violation across files, unclear naming, missing edge case test, unnecessary coupling | Yes |
| LOW | Minor improvement or style preference | Variable rename suggestion, comment improvement | No |
| INFO | Observation, context, or positive feedback | "Nice pattern," "FYI this also handles X" | No |

**Verdict rule:** APPROVE if no CRITICAL, HIGH, or MEDIUM findings. CHANGES_REQUESTED if any CRITICAL, HIGH, or MEDIUM findings exist. LOW and INFO are noted but do not block.

**In-cycle enforcement:** CHANGES_REQUESTED findings MUST be fixed in the current pipeline. The orchestrator is not permitted to downgrade findings to follow-up tickets, ship with known-broken security behavior, or ask the user whether to defer. See `protocols/pipeline-protocol.md` § In-Cycle Fix Rule. If a finding is genuinely orthogonal (different attack surface, different module), mark it INFO, not MEDIUM.

## Phase Output

```
Verdict: APPROVE / CHANGES_REQUESTED
Next: If BOTH code-review and security-review APPROVE → /harness:verify
      If CHANGES_REQUESTED → spawn engineer to fix → re-invoke BOTH review skills
Findings: [severity-rated findings: CRITICAL, HIGH, MEDIUM, LOW]
Agent summaries: [security-engineer's 2-3 sentence summary]
```
