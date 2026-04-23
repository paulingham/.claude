"""Dataclasses for the model-effectiveness analyser."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Observation:
    pipeline_id: str
    classification: str
    review_rounds: int
    rework: bool


@dataclass
class CostRecord:
    pipeline_id: str
    agent_role: str
    model_tier: str
    total_cost_usd: float


@dataclass
class Subcell:
    role: str
    classification: str
    tier: str
    obs: list = field(default_factory=list)
    total_cost: float = 0.0

    @property
    def n(self) -> int:
        return len(self.obs)


@dataclass
class CellDecision:
    role: str
    classification: str
    verdict: str
    from_tier: str | None = None
    to_tier: str | None = None
    max_n: int = 0
    subcells: list = field(default_factory=list)
