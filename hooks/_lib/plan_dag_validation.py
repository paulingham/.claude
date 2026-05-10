"""Validation rules 1-7 for plan_dag_resolver.

Canonical error tokens (verbatim — agents/architect.md § Validation Rules):

    1. cycle: [<ids>]
    2. dangling: [<ids>]
    3. self-dep: <id>
    4. bad-id-format: <id>
    5. duplicate-ids: [<ids>]
    6. empty plan
    7. empty-description: <id>

Each rule is a pure function over `PlanV2` returning a `list[str]` of error
tokens; the orchestrator and challengers grep these tokens. Functions return
empty lists on success — the public `validate()` aggregates and decides `ok`.
"""
from __future__ import annotations

import re
from collections import deque

# Kebab-case ID pattern (rule 4 — verbatim from architect.md).
_KEBAB_ID = re.compile(r"^[a-z][a-z0-9]*(-[a-z0-9]+)*$")


def check_empty_plan(plan) -> list[str]:
    return ["empty plan"] if not plan.slices else []


def check_kebab_ids(plan) -> list[str]:
    return [
        f"bad-id-format: {s.id}"
        for s in plan.slices
        if not _KEBAB_ID.match(s.id or "")
    ]


def check_duplicate_ids(plan) -> list[str]:
    seen: dict[str, int] = {}
    for s in plan.slices:
        seen[s.id] = seen.get(s.id, 0) + 1
    dups = sorted(sid for sid, count in seen.items() if count > 1)
    return [f"duplicate-ids: {dups}"] if dups else []


def check_self_deps(plan) -> list[str]:
    return [f"self-dep: {s.id}" for s in plan.slices if s.id in s.depends_on]


def check_dangling(plan) -> list[str]:
    declared = {s.id for s in plan.slices}
    missing: set[str] = set()
    for s in plan.slices:
        for dep in s.depends_on:
            if dep not in declared:
                missing.add(dep)
    return [f"dangling: {sorted(missing)}"] if missing else []


def check_empty_descriptions(plan) -> list[str]:
    return [
        f"empty-description: {s.id}"
        for s in plan.slices
        if not s.description.strip()
    ]


def build_indegree(plan):
    """Return (in_degree, children) maps for the plan's adjacency."""
    in_degree = {s.id: 0 for s in plan.slices}
    children: dict[str, list[str]] = {s.id: [] for s in plan.slices}
    for s in plan.slices:
        for dep in s.depends_on:
            if dep in in_degree:
                in_degree[s.id] += 1
                children[dep].append(s.id)
    return in_degree, children


def check_cycles(plan) -> list[str]:
    """Run Kahn; any node retaining in-degree > 0 sits on a cycle."""
    in_degree, children = build_indegree(plan)
    queue = deque(sid for sid, d in in_degree.items() if d == 0)
    processed: set[str] = set()
    while queue:
        node = queue.popleft()
        processed.add(node)
        for child in children[node]:
            in_degree[child] -= 1
            if in_degree[child] == 0:
                queue.append(child)
    on_cycle = sorted(sid for sid in in_degree if sid not in processed)
    return [f"cycle: {on_cycle}"] if on_cycle else []
