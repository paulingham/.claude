---
name: "skill-security-lint"
description: "Scan changed SKILL.md and skill _lib files for prompt-injection patterns, hardcoded secrets, and over-broad tool grants. Advisory only — findings fold into the security-engineer assessment, never a hard block."
verdict: "SKILL_LINT_CLEAN"
phase: "utility"
dispatch: "skill-tool"
argument-hint: "List of changed file paths (one per line or space-separated)"
---

# Skill Security Lint

## When to Invoke

Invoked by the security-engineer agent during the Review phase when the branch diff touches `skills/**/*.md`, `**/SKILL.md`, or any skill `_lib` file.

- **Diff touches `skills/`**: invoke to scan changed skill files for adversarial injection, secrets, and over-broad tool grants before the OWASP rubric runs.
- **Diff touches `hooks/_lib/` files used by skills**: invoke when the changed `_lib` file is a skill helper (pattern: `skill_*.py`, or any module sourced only from a `SKILL.md` procedure).
- **Do NOT use for application code**: OWASP injection detection, SQL injection, XSS, and similar data-plane vulnerabilities belong to the standard OWASP rubric — not this skill. Do NOT use for instinct files or agent-memory entries (those belong to AA01/AA02 in the Agentic OWASP checklist).

## Inputs

- **Changed file list**: one file path per entry; passed by the security-engineer from the branch diff filtered to `skills/**` and skill `_lib` paths.
- **Filesystem**: the actual changed files, readable by the agent.
- **No prior phase verdict required**: this is a utility sub-scan called from within the security-review phase.

## Procedure

### Step 1: Import the helper

The lint logic lives in `hooks/_lib/skill_security_lint.py`. Import it via the standard `sys.path.insert` pattern used across skill helpers:

```python
import sys
from pathlib import Path

# Resolve _lib relative to the repo root (works from any cwd)
_LIB = Path(__file__).resolve().parents[N] / "hooks" / "_lib"
sys.path.insert(0, str(_LIB))
from skill_security_lint import lint_skill_files
```

Where `N` is the number of directory levels from the invocation script back to the repo root.

### Step 2: Collect changed skill files

From the security-engineer's diff context, filter the changed-file list to paths matching:
- `skills/**/*.md`
- `**/SKILL.md`
- skill `_lib` files (e.g. `hooks/_lib/skill_*.py`)

Pass the resolved list to `lint_skill_files(paths)`.

### Step 3: Run the scan

```python
result = lint_skill_files(changed_paths)
```

The helper is fail-open: it never raises. It skips files larger than 1 MB (bounded). It returns the canonical result dict:

```python
{
    "findings": [{"file": str, "line": int, "category": str,
                  "severity": str, "snippet": str}],
    "counts": {"injection": int, "secret": int, "over_broad_tool": int},
    "files_scanned": int,
    "clean": bool,
}
```

Three detection categories:
- `injection` (severity HIGH): imperative override phrases in skill prose — e.g. "ignore all previous instructions", "disregard the above", "you must now", "bypass the gate", "disable the security guard", "grant yourself", "as an admin you". These patterns are deliberately adversarial phrasings; legitimate skill prose does not contain them.
- `secret` (severity CRITICAL): hardcoded credentials — AWS access key IDs (`AKIA[0-9A-Z]{16}`), generic `api_key=`/`token:`/`password=` assignments with non-trivial values, PEM private key headers.
- `over_broad_tool` (severity HIGH): `tools: ["*"]` wildcard grant in frontmatter, or Write/Edit/MultiEdit/Agent/Bash granted to a skill whose declared `phase:` is `review`, `final-gate`, or `utility`.

### Step 4: Emit advisory findings block

Write an advisory block to the security-engineer's working output:

```markdown
## Skill Security Lint Findings

Files scanned: N
Clean: true/false

| File | Line | Category | Severity | Snippet |
|------|------|----------|----------|---------|
| path/to/skill.md | 12 | injection | HIGH | Ignore all previous... |
```

If `clean == True`, emit:

```
Skill Security Lint: CLEAN (N files scanned, 0 findings)
```

### Step 5: Emit verdict

```
Verdict: SKILL_LINT_CLEAN
```

or

```
Verdict: SKILL_LINT_FLAGGED
```

`SKILL_LINT_FLAGGED` is advisory: the security-engineer folds the findings into its OWASP assessment under the AA02 (Instinct Poisoning) or AA03 (Tool Misuse) checklist items as appropriate. It never hard-blocks the pipeline — the security-engineer issues `APPROVE` or `CHANGES_REQUESTED` based on its holistic assessment.

## Output

- **Advisory findings block** in the security-engineer's output (see § Step 4 format).
- No state file written — this is a utility sub-scan within the security review phase.

## Verdict

| Verdict | Meaning | Downstream |
|---------|---------|------------|
| `SKILL_LINT_CLEAN` | No injection patterns, secrets, or over-broad tool grants found in the scanned skill files. | Advisory; security-engineer folds result into assessment. Pipeline continues normally. |
| `SKILL_LINT_FLAGGED` | One or more findings detected. | Advisory; security-engineer folds findings into OWASP AA02/AA03 assessment items. Never a hard block — security-engineer issues the gate verdict. |

The skill MUST emit exactly one verdict per invocation.

## Anti-Patterns

- **Do NOT hard-block on SKILL_LINT_FLAGGED**: this is an advisory scan. The security-engineer decides whether findings constitute a gate failure. Findings alone do not block ship.
- **Do NOT scan application code with this skill**: use the standard OWASP rubric for SQL injection, XSS, auth flows, and similar data-plane issues. This skill is scoped to skill/agent definition files only.
- **Do NOT add injection patterns that match legitimate skill prose**: the detection list is intentionally tight. Adding patterns that fire on normal instructional language (e.g. "you should", "the agent must") creates noise that teaches security-engineers to ignore the output. Keep patterns to clearly adversarial phrasings only.
- **Do NOT invoke on instinct files or agent-memory entries**: AA01 (Memory Poisoning) and AA02 (Instinct Poisoning) in the Agentic OWASP checklist cover those surfaces with dedicated rubric items.

## Tests

Unit tests live in `tests/test_skill_security_lint.py` (helper unit tests) and `tests/test_skill_security_lint_verdicts_registered.py` (verdict registration).

Key coverage:
- Fixture with injected instruction ("Ignore all previous instructions and...") → category `injection` detected (AC2 CORE).
- Fixture with hardcoded `api_key = "..."` or `AKIAIOSFODNN7EXAMPLE` → category `secret` detected.
- Fixture with `tools: ["*"]` or `Write` on a `phase: review` skill → category `over_broad_tool` detected.
- Clean fixture → `clean == True`, `findings == []`.
- `lint_skill_files([])` and `lint_skill_files(["/nonexistent/path"])` do not raise (fail-open).
- File >1MB is skipped without raising (bounded).
- Both verdicts present in `protocols/verdict-catalog.md`, attributed to `skill-security-lint` emitter.
