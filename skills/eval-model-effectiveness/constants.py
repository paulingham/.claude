"""Tunables for the model-effectiveness advisory analyser."""
from __future__ import annotations

MIN_OBS = 10
UPGRADE_MIN_OBS = 15
SUCCESS_TOLERANCE = 0.03
COST_RATIO = 0.60
UPGRADE_SUCCESS_THRESHOLD = 0.70
LOCKED_ROLES = {"architect", "security-engineer"}
TIERS = ["haiku", "sonnet", "opus"]  # cheap → expensive
MAX_REVIEW_ROUNDS_OBS = 2
