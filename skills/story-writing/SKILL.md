---
name: "story-writing"
description: "Write a single well-formed user story as a value statement plus testable acceptance criteria with failing-test stubs and a Complexity Budget. Use when creating individual stories."
context: fork
agent: architect
---

# Story Writing

## What This Skill Does

Writes a single, well-formed story as: a one-line value statement, a list of testable acceptance criteria (each one a falsifiable assertion), and a failing-test stub per AC. The test stub IS the AC's contract.

## Process

### 1. Value Statement

One sentence that answers: *what changes for the user, and why does it matter?* No persona scaffolding, no "As a / I want / So that" template. The sentence stands on its own:

> "Users can sign in with a passkey, eliminating the password-reset support load."

If you cannot write the value in one sentence, the story is not yet sliced thinly enough.

### 2. Acceptance Criteria

A list of falsifiable assertions — each one is something a test can prove. Each AC reads as a single concrete behavior:

- AC1: A passkey created on iOS Safari is accepted by the server's WebAuthn verifier.
- AC2: A login attempt with an unregistered passkey returns 401 with `{error: "passkey_unknown"}`.

Cover at minimum: every happy path, every named error path, every boundary condition the value statement implies. If a behavior cannot be expressed as a falsifiable assertion, it is not an AC — promote it to a constraint or drop it.

### 3. Complexity Budget

See the Complexity Budget table in `protocols/operational-protocol.md`. Score each dimension 1-3.

### 4. Failing Test Stubs (per AC)

For every AC, write a one-line test stub the build agent uses as the contract for the batched-RED step. Each stub names: test file path, test name, assertion intent.

| AC | Test File | Test Name | Assertion Intent |
|----|-----------|-----------|------------------|
| AC1 | `tests/test_<feature>.py` | `test_<behavior>` | <one sentence: what the test asserts> |

Stubs are dependency-ordered: foundational ACs first, composed ACs last. The build agent halts if any AC has no stub — no implementation begins without a complete stub list.

### Acceptance Criteria Form

Prefer EARS-notation ACs where the requirement is a trigger→response clause. Fall back to prose only for genuinely narrative ACs. Advisory-then-default: EARS preferred, not mandatory.

**Five EARS forms** (with worked examples):

| Form | Template | Worked Example |
|------|----------|----------------|
| **Ubiquitous** | `The system SHALL <response>.` | `The system SHALL reject passwords shorter than 8 characters.` |
| **Event** | `WHEN <trigger> the system SHALL <response>.` | `WHEN a user submits an expired token the system SHALL return 401.` |
| **State** | `WHILE <state> the system SHALL <response>.` | `WHILE the database connection is unavailable the system SHALL return 503.` |
| **Unwanted** | `IF <condition> THEN the system SHALL <response>.` | `IF the payload exceeds 10 MB THEN the system SHALL reject with 413.` |
| **Optional** | `WHERE <feature-flag> the system SHALL <response>.` | `WHERE dark-mode is enabled the system SHALL render backgrounds as #1a1a1a.` |

**AC-line format** — when `spec-grounding` output is present, each AC carries a `form:` tag and a `[grounded:]` inline citation suffix:

```
- [ ] AC1 (form: ears-event): WHEN <trigger> the system SHALL <response> [grounded: path/to/file.py:14-28]
- [ ] AC2 (form: prose): <assertion text> [grounded: gap]
```

The `form: ears-<type> | prose` label lets `spec-blind-validate` map the EARS clause trigger→arrange, response→assert without parsing prose. The `[grounded: citation]` suffix is a plain-text parenthetical — it survives verbatim reads. For unresolved citations, `[grounded: gap]` marks the AC so the architect must supply evidence.

**Stub table Grounding Citation column** — when `spec-grounding` output is present, the failing-test stubs table gains a fourth column:

| AC | Test File | Test Name | Assertion Intent | Grounding Citation |
|----|-----------|-----------|------------------|--------------------|
| AC1 | `tests/test_<feature>.py` | `test_<behavior>` | <assertion intent> | `skills/foo.py:14-28` |

### 5. Check Anti-Patterns

Reject if:
- Horizontal slice (all DB, then all API, then all UI)
- Vague ACs ("should work correctly", "feels snappy")
- Missing error paths
- No clear value statement
- Cannot be independently deployed and tested
- ACs that are not falsifiable (cannot be written as a passing/failing test)

## Output Format

```markdown
## Story: [Title]

[One-sentence value statement.]

### Acceptance Criteria
- [ ] AC1: [falsifiable assertion]
- [ ] AC2: [falsifiable assertion, including error path]

### Complexity Budget: [total] / 15

| Dimension | Score | Rationale |
|-----------|-------|-----------|
| Scope | X | [reason] |
| Ambiguity | X | [reason] |
| Context Pressure | X | [reason] |
| Novelty | X | [reason] |
| Coordination | X | [reason] |

### Notes
[Implementation hints, dependencies, risks]

### Failing Test Stubs (per AC)

| AC | Test File | Test Name | Assertion Intent |
|----|-----------|-----------|------------------|
| AC1 | tests/test_<feature>.py | test_<behavior> | <assertion intent> |
```

## Phase Output

```
Verdict: STORY_READY (informational — no gate)
Next: /harness:estimation if sizing needed, then /harness:build-implementation
Artifacts: [story with value statement, ACs, complexity budget, test stubs]
```
