"""Slice slice-b-helper-module: hooks/_lib/plan_dag_resolver.py contract.

Public API (per agents/architect.md § Helper Module):

- Slice          — frozen dataclass(id, depends_on, description, domain)
- PlanV2         — frozen dataclass(schema_version, task_id, slices)
- ValidateResult — frozen dataclass(ok, errors)
- parse_plan(path)        -> PlanV2 | ValidateResult     (rejects v1)
- validate(plan)          -> ValidateResult              (rules 1-7)
- topological_waves(plan) -> list[list[str]]             (Kahn's algorithm)

Validation rules carry canonical error tokens documented in agents/architect.md
(verbatim — orchestrator and challengers grep these tokens):

    1. cycle: [<ids>]
    2. dangling: [<ids>]
    3. self-dep: <id>
    4. bad-id-format: <id>
    5. duplicate-ids: [<ids>]
    6. empty plan
    7. empty-description: <id>

Plus AC4 IO error structures (file-missing, malformed-yaml, missing-slices-key)
and AC1/AC2 PBT stubs (Tier 1.5 properties — manual fuzz fallback because
hypothesis is not on this harness).
"""
import unittest
from dataclasses import FrozenInstanceError, fields
from pathlib import Path
from typing import get_type_hints

from plan_dag_resolver import (
    PlanV2,
    Slice,
    ValidateResult,
    parse_plan,
    topological_waves,
    validate,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_DIR = REPO_ROOT / "tests" / "fixtures" / "plan_dag"


def _fixture(name: str) -> str:
    return str(FIXTURE_DIR / name)


# ---------------------------------------------------------------- AC1 surface


class PublicApiSurface(unittest.TestCase):
    """AC1 — Public-API spec: dataclass shapes + signatures match agents/architect.md."""

    def test_slice_dataclass_is_frozen_with_required_fields(self):
        slice_obj = Slice(id="a", depends_on=("b",), description="d")
        with self.assertRaises(FrozenInstanceError):
            slice_obj.id = "x"  # type: ignore[misc]
        names = {f.name for f in fields(Slice)}
        self.assertEqual(names, {"id", "depends_on", "description", "domain"})

    def test_slice_domain_default_is_none(self):
        slice_obj = Slice(id="a", depends_on=(), description="d")
        self.assertIsNone(slice_obj.domain)

    def test_planv2_dataclass_is_frozen_with_required_fields(self):
        plan = PlanV2(schema_version=2, task_id="t", slices=())
        with self.assertRaises(FrozenInstanceError):
            plan.task_id = "x"  # type: ignore[misc]
        names = {f.name for f in fields(PlanV2)}
        self.assertEqual(names, {"schema_version", "task_id", "slices"})

    def test_validate_result_dataclass_is_frozen(self):
        result = ValidateResult(ok=True, errors=())
        with self.assertRaises(FrozenInstanceError):
            result.ok = False  # type: ignore[misc]
        names = {f.name for f in fields(ValidateResult)}
        self.assertEqual(names, {"ok", "errors"})

    def test_public_api_signatures_match_spec(self):
        # Callable existence + argument names
        self.assertTrue(callable(parse_plan))
        self.assertTrue(callable(validate))
        self.assertTrue(callable(topological_waves))
        hints_parse = get_type_hints(parse_plan)
        self.assertIn("path", hints_parse)
        hints_topo = get_type_hints(topological_waves)
        self.assertIn("plan", hints_topo)


# ----------------------------------------------------------- v1-rejection (B4)


class ParsePlanRejectsV1(unittest.TestCase):
    """B4 fix — helper is v2-only; v1 plans must use the legacy dispatch path."""

    def test_parse_plan_rejects_v1_input(self):
        result = parse_plan(_fixture("v1_legacy_plan.md"))
        self.assertIsInstance(result, ValidateResult)
        self.assertFalse(result.ok)
        joined = " ".join(result.errors)
        self.assertIn("v1 plans must be dispatched via legacy path", joined)

    def test_parse_plan_rejects_explicit_v1(self):
        result = parse_plan(_fixture("v1_explicit.md"))
        self.assertIsInstance(result, ValidateResult)
        self.assertFalse(result.ok)


# --------------------------------------------------- AC4 structured error paths


class ParsePlanIoErrors(unittest.TestCase):
    """AC4 — never raises; all error paths return ValidateResult."""

    def test_missing_plan_file_returns_structured_error(self):
        result = parse_plan("/nonexistent/path/plan.md")
        self.assertIsInstance(result, ValidateResult)
        self.assertFalse(result.ok)

    def test_malformed_yaml_block_returns_structured_error(self):
        result = parse_plan(_fixture("v2_malformed_yaml.md"))
        self.assertIsInstance(result, ValidateResult)
        self.assertFalse(result.ok)

    def test_missing_slices_key_returns_structured_error(self):
        result = parse_plan(_fixture("v2_missing_slices.md"))
        self.assertIsInstance(result, ValidateResult)
        self.assertFalse(result.ok)


# -------------------------------------------------- topological_waves examples


class TopologicalWavesFixtures(unittest.TestCase):
    """AC2 — wave shape on canonical fixtures."""

    def test_v2_single_slice_yields_one_wave_one_slice(self):
        plan = parse_plan(_fixture("v2_single_slice.md"))
        self.assertIsInstance(plan, PlanV2)
        self.assertEqual(topological_waves(plan), [["only"]])

    def test_v2_diamond_yields_three_waves(self):
        plan = parse_plan(_fixture("v2_diamond.md"))
        self.assertIsInstance(plan, PlanV2)
        waves = topological_waves(plan)
        self.assertEqual(len(waves), 3)
        self.assertEqual(waves[0], ["r"])
        self.assertEqual(sorted(waves[1]), ["a", "b"])
        self.assertEqual(waves[2], ["d"])

    def test_v2_chain_serialises(self):
        plan = parse_plan(_fixture("v2_chain.md"))
        self.assertIsInstance(plan, PlanV2)
        self.assertEqual(topological_waves(plan), [["a"], ["b"], ["c"]])

    def test_v2_independent_co_runnable(self):
        plan = parse_plan(_fixture("v2_independent.md"))
        self.assertIsInstance(plan, PlanV2)
        waves = topological_waves(plan)
        self.assertEqual(len(waves), 1)
        self.assertEqual(sorted(waves[0]), ["a", "b", "c"])


# ----------------------------------------------------- validate rule fixtures


class ValidateRuleFixtures(unittest.TestCase):
    """AC2 + AC5 — every validation rule has a fixture and a token assertion."""

    def _parsed(self, name: str) -> PlanV2:
        plan = parse_plan(_fixture(name))
        self.assertIsInstance(plan, PlanV2, f"{name} should parse to PlanV2")
        return plan  # type: ignore[return-value]

    def test_v2_cycle_validates_false(self):
        result = validate(self._parsed("v2_cycle.md"))
        self.assertFalse(result.ok)
        self.assertTrue(any("cycle" in e for e in result.errors))

    def test_v2_dangling_validates_false(self):
        result = validate(self._parsed("v2_dangling.md"))
        self.assertFalse(result.ok)
        self.assertTrue(any("dangling" in e for e in result.errors))

    def test_v2_self_dep_validates_false(self):
        result = validate(self._parsed("v2_self_dep.md"))
        self.assertFalse(result.ok)
        self.assertTrue(any("self-dep" in e for e in result.errors))

    def test_v2_dup_id_validates_false(self):
        result = validate(self._parsed("v2_dup_id.md"))
        self.assertFalse(result.ok)
        self.assertTrue(any("duplicate-ids" in e for e in result.errors))

    def test_v2_bad_id_validates_false(self):
        result = validate(self._parsed("v2_bad_id.md"))
        self.assertFalse(result.ok)
        self.assertTrue(any("bad-id-format" in e for e in result.errors))

    def test_v2_empty_description_validates_false(self):
        result = validate(self._parsed("v2_empty_description.md"))
        self.assertFalse(result.ok)
        self.assertTrue(any("empty-description" in e for e in result.errors))

    def test_v2_empty_slices_validates_false(self):
        result = validate(self._parsed("v2_empty_slices.md"))
        self.assertFalse(result.ok)
        self.assertTrue(any("empty plan" in e for e in result.errors))

    def test_validate_passes_clean_diamond(self):
        result = validate(self._parsed("v2_diamond.md"))
        self.assertTrue(result.ok, f"diamond should validate; got {result.errors}")
        self.assertEqual(result.errors, ())


# ---------------------------------------------------- PBT (manual fuzz) stubs


def _build_plan_from_edges(slice_ids, edges):
    """Build a PlanV2 from a list of slice ids and edges (parent, child)."""
    deps = {sid: [] for sid in slice_ids}
    for parent, child in edges:
        deps[child].append(parent)
    slices = tuple(
        Slice(id=sid, depends_on=tuple(deps[sid]), description=f"slice {sid}")
        for sid in slice_ids
    )
    return PlanV2(schema_version=2, task_id="pbt", slices=slices)


def _has_cycle(slice_ids, edges):
    """Reference cycle detector for the oracle property."""
    graph = {sid: [] for sid in slice_ids}
    for parent, child in edges:
        graph[parent].append(child)
    WHITE, GRAY, BLACK = 0, 1, 2
    color = {sid: WHITE for sid in slice_ids}

    def visit(node):
        color[node] = GRAY
        for nxt in graph[node]:
            if color[nxt] == GRAY:
                return True
            if color[nxt] == WHITE and visit(nxt):
                return True
        color[node] = BLACK
        return False

    return any(color[sid] == WHITE and visit(sid) for sid in slice_ids)


def _random_dag(rng, size):
    """Generate a random valid DAG with `size` nodes; edges respect topo order."""
    ids = [f"n{i}" for i in range(size)]
    edges = []
    for child_idx in range(size):
        for parent_idx in range(child_idx):
            if rng.random() < 0.3:
                edges.append((ids[parent_idx], ids[child_idx]))
    return ids, edges


class PropertyBasedTests(unittest.TestCase):
    """B5 fix — Tier 1.5 properties. Manual fuzz fallback (no hypothesis)."""

    SAMPLES = 50

    def setUp(self):
        import random
        # Seed for reproducibility of any failing case
        self.rng = random.Random(20260510)

    def test_pbt_topological_waves_respects_edges(self):
        """For every edge (u, v) in p.edges: wave_index(u) < wave_index(v)."""
        for _ in range(self.SAMPLES):
            size = self.rng.randint(1, 10)
            ids, edges = _random_dag(self.rng, size)
            plan = _build_plan_from_edges(ids, edges)
            self.assertTrue(validate(plan).ok)
            waves = topological_waves(plan)
            wave_index = {sid: i for i, w in enumerate(waves) for sid in w}
            for parent, child in edges:
                self.assertLess(
                    wave_index[parent], wave_index[child],
                    f"edge {parent}->{child} violates topological order",
                )

    def test_pbt_topological_waves_partition(self):
        """Every slice appears in exactly one wave; union covers all ids."""
        for _ in range(self.SAMPLES):
            size = self.rng.randint(1, 10)
            ids, edges = _random_dag(self.rng, size)
            plan = _build_plan_from_edges(ids, edges)
            waves = topological_waves(plan)
            seen = [sid for wave in waves for sid in wave]
            self.assertEqual(sorted(seen), sorted(ids))
            self.assertEqual(len(seen), len(set(seen)))  # no duplicates

    def test_pbt_validate_idempotent(self):
        """validate(p) == validate(p) — pure function, no internal state."""
        for _ in range(self.SAMPLES):
            size = self.rng.randint(1, 10)
            ids, edges = _random_dag(self.rng, size)
            plan = _build_plan_from_edges(ids, edges)
            r1 = validate(plan)
            r2 = validate(plan)
            self.assertEqual(r1, r2)

    def test_pbt_cycle_detection_oracle(self):
        """validate.ok matches reference cycle detector."""
        # Deliberately mix valid DAGs with synthetic cycles
        for trial in range(self.SAMPLES):
            size = self.rng.randint(2, 8)
            ids, edges = _random_dag(self.rng, size)
            # Inject a cycle 50% of the time by reversing one edge
            cyclic = trial % 2 == 0 and edges
            if cyclic:
                parent, child = edges[0]
                edges = list(edges) + [(child, parent)]
            plan = _build_plan_from_edges(ids, edges)
            expected_cycle = _has_cycle(ids, edges)
            result = validate(plan)
            if expected_cycle:
                self.assertFalse(
                    result.ok,
                    f"reference says cycle, validate says ok: {ids} {edges}",
                )
                self.assertTrue(any("cycle" in e for e in result.errors))
            # Non-cyclic plans may still fail other rules (none here, since
            # generator only produces well-formed kebab ids), so only assert
            # the cycle direction.

    def test_pbt_validate_then_topological_oracle(self):
        """validate(p).ok ⇒ topological_waves(p) is non-empty AND covers all slices."""
        # Metamorphic property covering parse_plan round-trip intent: a plan
        # that validates must produce a wave layout covering every slice.
        for _ in range(self.SAMPLES):
            size = self.rng.randint(1, 10)
            ids, edges = _random_dag(self.rng, size)
            plan = _build_plan_from_edges(ids, edges)
            if validate(plan).ok:
                waves = topological_waves(plan)
                self.assertTrue(waves, "non-empty plan should have ≥1 wave")
                covered = {sid for w in waves for sid in w}
                self.assertEqual(covered, set(ids))


if __name__ == "__main__":
    unittest.main()
