"""AC8 — runner contract: validator + plumbing only, no LLM call.

Per § 6.1 / § 6.4: the agent IS the LLM caller (skill § 0.3 contains the
iteration loop). `sast_triage.py` exposes `triage_finding(parsed_model_output)`
as a validator entry point, but does NOT itself invoke any LLM.

This test asserts:
  (i)  `triage_finding` exists and is callable as `(dict) -> dict`
       returning the validated `{verdict, rationale}` from
       `validate_triage_output`. Finding metadata is bound to decision
       records by callers via `write_decision_jsonl`.
  (ii) `sast_triage.py` source contains NO LLM-call surface (no
       `anthropic`, `openai`, `claude`, `requests.post`, `urllib`, etc.).
  (iii) Given N findings, the validator pathway can be invoked N times —
        producing N `{verdict, rationale}` results — with no internal
        fan-out, no batching collapse.
"""
import inspect
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "hooks" / "_lib"))

import sast_triage
from sast_triage import triage_finding


def test_triage_finding_validates_per_call():
    """AC8(i,iii) — N model outputs → N validated results, no batching."""
    long_rationale = "This is a real path-traversal sink reachable from the request body parser."
    model_outputs = [
        {"verdict": "keep", "rationale": long_rationale},
        {"verdict": "drop",
         "rationale": "This is in a test fixture mocking the database driver, not production."},
        {"verdict": "unsure", "rationale": "Could not determine without context on the calling site."},
    ]
    results = [triage_finding(out) for out in model_outputs]
    assert len(results) == 3
    assert results[0]["verdict"] == "keep"
    assert results[1]["verdict"] == "drop"
    assert results[2]["verdict"] == "unsure"


def test_triage_finding_signature_is_dict_to_dict():
    """AC8(i) — entry point exposes single (parsed_model_output) parameter."""
    sig = inspect.signature(triage_finding)
    params = list(sig.parameters)
    assert len(params) == 1, f"expected 1 param, got {params}"


def test_sast_triage_module_does_not_call_llm():
    """AC8(ii) — module does NOT import or call LLM clients."""
    source = Path(sast_triage.__file__).read_text()
    forbidden = [
        "import anthropic",
        "from anthropic",
        "import openai",
        "from openai",
        "requests.post",
        "urllib.request",
        "http.client",
        ".messages.create",
    ]
    for needle in forbidden:
        assert needle not in source, (
            f"sast_triage.py must not invoke LLM (found {needle!r})"
        )
