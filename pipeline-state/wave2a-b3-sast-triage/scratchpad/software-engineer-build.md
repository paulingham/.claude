---
category: discovery
---

`hooks/_lib/sast_triage.py` was originally written as a single 635-line module
and was BLOCKED by the code-shape PostToolUse hook (300-line cap). Decomposed
into 5 sibling modules:

- `sast_triage.py` (91 lines) — public API + top-level orchestrator
- `sast_triage_constants.py` (46 lines) — module constants
- `sast_triage_parser.py` (137 lines) — SARIF parser, severity, validator
- `sast_triage_detection.py` (147 lines) — 4-rung detection ladder
- `sast_triage_telemetry.py` (93 lines) — JSONL writers
- `sast_triage_render.py` (169 lines) — merge-block + AC18 audit

All under 300 lines individually. Future contributors: the public re-export
in `sast_triage.py` IS the consumer-facing surface — internal modules can
move freely.

---
category: pattern
---

The `_check_candidate` extraction in `sast_triage_render.py::audit_agent_output`
turned a deeply-nested loop (4-level conditional) into a single early-return
helper returning a violation reason or None. This is the pattern when
"compute violation reason" is fundamentally a sequential rule chain.

---
category: warning
---

`hooks/_lib/jsonl-emit.sh` argv pattern was MIRRORED in pure Python via
`_emit_jsonl(outfile, **fields)` (kwargs-only, never shell-interpolated).
Future telemetry hooks: don't reach for `subprocess.run` to call the shell
helper from Python — use the kwargs API directly. Cross-process boundary
is unnecessary overhead.

---
category: fragility
---

Test inheritance from a stalled candidate worktree: the inherited
`tests/test_sast_triage_*.py` files imported `from sast_triage import ...`
without sys.path setup. Fixed by adding
`sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "hooks" / "_lib"))`
to each test file (matches the existing convention in
`tests/test_agent_instinct_categories_loader.py`). No conftest.py exists in
this repo by design (per plan § 6.4).
