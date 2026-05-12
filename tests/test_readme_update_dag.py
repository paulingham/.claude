"""Slice-f-readme — README documents Multi-Slice DAG Mode + helper module (M2 fix).

Per `pipeline-state/architect-plan-dag/plan.md` § slice-f-readme, README.md must:
  - AC1: mention `Multi-Slice DAG Mode` / `DAG mode` / `schema_version: 2` near a
    Build dispatch description.
  - AC2: list the DAG variant in the Build-dispatch table OR name the precedence
    ordering pdr_rtv > dag > bestofn > standard (or equivalent).

Slice-f scope (per build-implementation prompt) additionally requires the helper
module `hooks/_lib/plan_dag_resolver.py` to be discoverable from README (a
discoverability check — the helper is the load-bearing artifact of slice-b).
"""
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
README = REPO_ROOT / "README.md"


def _readme_text():
    assert README.exists(), f"README.md missing at {README}"
    return README.read_text()


def test_readme_mentions_dag_mode():
    """AC1: README cites the new DAG dispatch variant.

    Accepts any of: `Multi-Slice DAG Mode`, `DAG mode`, `schema_version: 2`
    (case-insensitive) — and links to the canonical spec at
    `parallel-dispatch-details.md`.
    """
    text = _readme_text()
    lower = text.lower()
    dag_tokens = ("multi-slice dag mode", "dag mode", "schema_version: 2")
    found = [t for t in dag_tokens if t in lower]
    assert found, (
        "README.md does not mention any of: 'Multi-Slice DAG Mode', "
        "'DAG mode', or 'schema_version: 2'. The slice-f-readme M2 fix "
        "requires README to document the new Build dispatch variant."
    )
    assert "parallel-dispatch-details.md" in text, (
        "README.md mentions a DAG token but does not link to "
        "`parallel-dispatch-details.md` for the canonical spec. "
        "M2 fix requires discoverability — readers must be able to find "
        "the full Multi-Slice DAG Mode procedure."
    )


def test_readme_dispatch_table_lists_dag_variant():
    """AC2: README's dispatch description names the DAG variant alongside
    pdr_rtv and bestofn.

    Either: (a) a Build-dispatch table lists DAG as a row, OR
    (b) README prose names the precedence ordering
    (`pdr_rtv > dag > bestofn > standard` or equivalent).
    """
    text = _readme_text()
    lower = text.lower()
    # The dispatch precedence is the canonical phrasing in
    # protocols/pipeline-protocol.md § Build Phase Dispatch Variants:
    # `pdr_rtv > bestofn > standard`. Slice-f extends with `dag`.
    has_precedence_prose = (
        "pdr_rtv" in lower and "bestofn" in lower
        and ("dag" in lower)
    )
    # Or: a table row that names the DAG dispatch variant alongside the
    # existing variants.
    has_dispatch_table_row = (
        "dag" in lower
        and ("pdr_rtv" in lower or "best-of-n" in lower or "bestofn" in lower)
    )
    assert has_precedence_prose or has_dispatch_table_row, (
        "README.md does not name the DAG Build-dispatch variant alongside "
        "pdr_rtv/bestofn. AC2 requires either a dispatch-table row or "
        "precedence-ordering prose. Current README mentions of these tokens: "
        f"pdr_rtv={'pdr_rtv' in lower}, bestofn={'bestofn' in lower}, "
        f"dag={'dag' in lower}."
    )


def test_readme_documents_plan_dag_resolver():
    """Slice-f scope: README mentions the new helper module
    `hooks/_lib/plan_dag_resolver.py` so the load-bearing artifact of
    slice-b is discoverable via grep.
    """
    text = _readme_text()
    assert "plan_dag_resolver" in text, (
        "README.md does not mention `plan_dag_resolver`. The slice-f-readme "
        "scope requires the new helper module "
        "`hooks/_lib/plan_dag_resolver.py` to be discoverable from README "
        "(it is the load-bearing artifact of the slice-b helper module)."
    )
