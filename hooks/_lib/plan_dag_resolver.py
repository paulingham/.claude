"""Plan DAG resolver — schema_version: 2 only.

Parses `pipeline-state/{task-id}/plan.md` plans that carry the v2 DAG schema,
validates them against rules 1-7, and emits topologically-ordered waves of
co-runnable slices via Kahn's algorithm.

The module is **v2-only**: `parse_plan` rejects v1 inputs (no `schema_version`
or `schema_version: 1`) with a structured `ValidateResult`. v1 plans are
dispatched via the orchestrator's legacy multi-slice path; the orchestrator
runs `detect_plan_schema_version()` BEFORE invoking `parse_plan` and never
calls into this module for v1.

Public API (frozen — agents/architect.md § Helper Module is the contract):

- `Slice(id, depends_on, description, domain=None)`
- `PlanV2(schema_version, task_id, slices)`
- `ValidateResult(ok, errors)`
- `parse_plan(path) -> PlanV2 | ValidateResult`
- `validate(plan) -> ValidateResult` — runs rules 1-7
- `topological_waves(plan) -> list[list[str]]` — Kahn, in-degree 0 each pass

Validation tokens live in `plan_dag_validation` — verbatim from architect.md.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal, Union

import yaml

from plan_dag_validation import (
    build_indegree,
    check_cycles,
    check_dangling,
    check_duplicate_ids,
    check_empty_descriptions,
    check_empty_plan,
    check_kebab_ids,
    check_self_deps,
)

# Rejected fields — reserved for v3+ per architect.md § Future-reserved fields
_FORBIDDEN_FIELDS = {"mode", "cap_hint"}

V1_REJECT_MSG = "v1 plans must be dispatched via legacy path; helper is v2-only"


@dataclass(frozen=True)
class Slice:
    id: str
    depends_on: tuple[str, ...]
    description: str
    domain: str | None = None


@dataclass(frozen=True)
class PlanV2:
    schema_version: Literal[2]
    task_id: str
    slices: tuple[Slice, ...]


@dataclass(frozen=True)
class ValidateResult:
    ok: bool
    errors: tuple[str, ...] = field(default=())


# ----------------------------------------------------------------- I/O helpers


def _read_text(path: str) -> str | None:
    try:
        return Path(path).read_text()
    except (OSError, FileNotFoundError):
        return None


def _split_frontmatter(text: str) -> tuple[dict | None, str]:
    """Return (frontmatter_dict, body); fm None on missing/parse-error."""
    if not text.startswith("---"):
        return None, text
    end = text.find("\n---", 3)
    if end < 0:
        return None, text
    fm_text = text[3:end].lstrip("\n")
    body = text[end + 4 :]
    try:
        fm = yaml.safe_load(fm_text) or {}
    except yaml.YAMLError:
        return None, body
    return (fm if isinstance(fm, dict) else None), body


def _extract_slices_yaml(body: str) -> str | None:
    """Find the first fenced ```yaml block under a `## Slices` heading."""
    pattern = re.compile(
        r"^##\s+Slices\s*$.*?^```yaml\s*\n(.*?)^```",
        re.MULTILINE | re.DOTALL,
    )
    match = pattern.search(body)
    return match.group(1) if match else None


# ------------------------------------------------------------ slice construction


def _coerce_slice(raw: dict) -> Slice:
    """Build a Slice from a YAML dict; tolerates missing optional fields."""
    deps = raw.get("depends-on", [])
    if not isinstance(deps, list):
        deps = []
    return Slice(
        id=str(raw.get("id", "")),
        depends_on=tuple(str(d) for d in deps),
        description=str(raw.get("description", "")),
        domain=raw.get("domain"),
    )


def _has_forbidden_field(raw: dict) -> bool:
    return any(key in raw for key in _FORBIDDEN_FIELDS)


def _parse_slices_block(yaml_text: str) -> tuple[tuple[Slice, ...] | None, str | None]:
    """Return (slices, error). slices is None iff YAML is malformed or shape wrong."""
    try:
        parsed = yaml.safe_load(yaml_text)
    except yaml.YAMLError as exc:
        return None, f"malformed-yaml: {exc.__class__.__name__}"
    if not isinstance(parsed, dict) or "slices" not in parsed:
        return None, "missing slices key in YAML codeblock"
    raw_list = parsed.get("slices")
    if not isinstance(raw_list, list):
        return None, "slices must be a list"
    slices = []
    for raw in raw_list:
        if not isinstance(raw, dict):
            return None, "each slice must be a YAML mapping"
        if _has_forbidden_field(raw):
            forbidden = sorted(set(raw) & _FORBIDDEN_FIELDS)
            return None, f"forbidden v3+ field(s) in slice: {forbidden}"
        slices.append(_coerce_slice(raw))
    return tuple(slices), None


# --------------------------------------------------------------- public parse_plan


def parse_plan(path: str) -> Union[PlanV2, ValidateResult]:
    """Parse a v2 plan from disk. Returns ValidateResult(ok=False, ...) on:
       - file missing
       - frontmatter missing or schema_version absent (treated as v1)
       - schema_version != 2 (v1 explicit, v3+ unknown)
       - missing `## Slices` YAML codeblock
       - YAML parse error
       - forbidden v3+ fields present (`mode`, `cap_hint`)

    Orchestrator MUST run `detect_plan_schema_version()` FIRST and only call
    `parse_plan` when version == 2. v1 inputs are rejected here as defence-in-
    depth — the helper is v2-only by contract.
    """
    text = _read_text(path)
    if text is None:
        return ValidateResult(ok=False, errors=(f"plan file not found: {path}",))

    fm, body = _split_frontmatter(text)
    if fm is None:
        return ValidateResult(ok=False, errors=("malformed frontmatter",))

    if fm.get("schema_version") != 2:
        # v1 (absent or =1) and v3+ (>2) both rejected — helper is v2-only.
        return ValidateResult(ok=False, errors=(V1_REJECT_MSG,))

    yaml_block = _extract_slices_yaml(body)
    if yaml_block is None:
        return ValidateResult(
            ok=False, errors=("missing `## Slices` YAML codeblock",)
        )

    slices, err = _parse_slices_block(yaml_block)
    if slices is None:
        return ValidateResult(ok=False, errors=(err or "yaml parse failure",))

    return PlanV2(
        schema_version=2,
        task_id=str(fm.get("task_id", "")),
        slices=slices,
    )


# ------------------------------------------------------- validate (rules 1-7)


def validate(plan: PlanV2) -> ValidateResult:
    """Apply rules 1-7. Empty plan short-circuits (rule 6); structural errors
    surface before the cycle check so a malformed plan does not produce noisy
    nested cycle errors."""
    if empty := check_empty_plan(plan):
        return ValidateResult(ok=False, errors=tuple(empty))

    structural: list[str] = []
    structural += check_kebab_ids(plan)
    structural += check_duplicate_ids(plan)
    structural += check_self_deps(plan)
    structural += check_dangling(plan)
    structural += check_empty_descriptions(plan)
    if structural:
        return ValidateResult(ok=False, errors=tuple(structural))

    cycle_errors = check_cycles(plan)
    return ValidateResult(ok=not cycle_errors, errors=tuple(cycle_errors))


# ----------------------------------------------------- topological_waves (Kahn)


def topological_waves(plan: PlanV2) -> list[list[str]]:
    """Kahn's algorithm — each wave is the current zero-in-degree front.

    Slices within a wave are returned in declaration order to keep output
    deterministic for tests. Co-runnable slices share a wave; dependent
    slices land in later waves. Caller assumes plan has already passed
    `validate(plan).ok`; on a cyclic plan the wave list ends before all
    slices are emitted (used internally by the cycle check)."""
    in_degree, children = build_indegree(plan)
    order = {s.id: i for i, s in enumerate(plan.slices)}
    waves: list[list[str]] = []
    ready = sorted(
        (sid for sid, d in in_degree.items() if d == 0),
        key=lambda sid: order[sid],
    )
    while ready:
        waves.append(ready)
        next_ready: list[str] = []
        for sid in ready:
            for child in children[sid]:
                in_degree[child] -= 1
                if in_degree[child] == 0:
                    next_ready.append(child)
        ready = sorted(next_ready, key=lambda s: order[s])
    return waves
