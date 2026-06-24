"""Equivalence-proof: migrated agent frontmatter aliases resolve to expected concrete IDs.

Each batch adds rows. Reads live frontmatter, resolves via resolve_model_alias,
asserts the expected concrete ID (with four documented deltas vs pre-migration).

Four documented intentional deltas:
  1. architect + infra executor: 4-7 → 4-8 (Batch A, APPROVED bump)
  2. all 7 Batch-B advisors: 4-7 → 4-8 (SSOT: strong = claude-opus-4-8)
  3. plan-cache-adapter executor: bare haiku → datestamped (Batch D canonicalization)
  4. executor_resolver.py force-opus path: 4-7 → 4-8 (Batch E, SSOT alignment)
"""
import re
import unittest
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
AGENTS_DIR = REPO_ROOT / "agents"

STRONG = "claude-opus-4-8"
MID = "claude-sonnet-4-6"
CHEAP = "claude-haiku-4-5-20251001"


def _frontmatter(role):
    from model_alias import resolve_model_alias as _resolve
    text = (AGENTS_DIR / f"{role}.md").read_text()
    match = re.match(r"^---\n(.*?)\n---", text, re.DOTALL)
    fm = yaml.safe_load(match.group(1)) if match else {}
    return fm, _resolve


# ---------------------------------------------------------------------------
# Batch A — Opus executors → `strong`
# ---------------------------------------------------------------------------

class BatchAArchitectOpusExecutor(unittest.TestCase):
    def test_architect_resolves_strong_to_opus_4_8(self):
        from model_alias import resolve_model_alias
        fm, _ = _frontmatter("architect")
        self.assertEqual(fm["executor"], "strong",
                         "architect executor must be alias 'strong'")
        self.assertEqual(resolve_model_alias(fm["executor"]), STRONG,
                         "alias 'strong' must resolve to claude-opus-4-8")
        self.assertEqual(fm["advisor"], "none",
                         "architect advisor must remain 'none'")

    def test_infra_engineer_resolves_strong_to_opus_4_8(self):
        from model_alias import resolve_model_alias
        fm, _ = _frontmatter("infrastructure-engineer")
        self.assertEqual(fm["executor"], "strong",
                         "infrastructure-engineer executor must be alias 'strong'")
        self.assertEqual(resolve_model_alias(fm["executor"]), STRONG,
                         "alias 'strong' must resolve to claude-opus-4-8")
        self.assertEqual(fm["advisor"], "none",
                         "infrastructure-engineer advisor must remain 'none'")

    def test_architect_model_field_unchanged_opus(self):
        fm, _ = _frontmatter("architect")
        self.assertEqual(fm["model"], "opus",
                         "architect model: field must remain literal 'opus'")


# ---------------------------------------------------------------------------
# Batch B — Sonnet exec + Opus advisor → `mid`/`strong`
# ---------------------------------------------------------------------------

class BatchBAdvisorCards(unittest.TestCase):
    def test_batch_b_advisor_cards_resolve(self):
        from model_alias import resolve_model_alias
        for role in ("vlm-critic", "sandbox-verify-engineer"):
            with self.subTest(role=role):
                fm, _ = _frontmatter(role)
                self.assertEqual(fm["executor"], "mid",
                                 f"{role} executor must be alias 'mid'")
                self.assertEqual(resolve_model_alias(fm["executor"]), MID,
                                 f"alias 'mid' must resolve to {MID}")
                self.assertEqual(fm["advisor"], "strong",
                                 f"{role} advisor must be alias 'strong'")
                self.assertEqual(resolve_model_alias(fm["advisor"]), STRONG,
                                 f"alias 'strong' must resolve to {STRONG}")

    def test_batch_b_advisor_was_opus_4_7_now_4_8(self):
        """All 7 Batch-B advisors previously carried claude-opus-4-7; now resolve to 4-8."""
        from model_alias import resolve_model_alias
        batch_b_roles = (
            "software-engineer",
            "frontend-engineer",
            "spec-blind-validator",
            "security-engineer",
            "vlm-critic",
            "sandbox-verify-engineer",
            "patch-critic",
        )
        for role in batch_b_roles:
            with self.subTest(role=role):
                fm, _ = _frontmatter(role)
                self.assertEqual(fm["advisor"], "strong",
                                 f"{role} advisor must be alias 'strong'")
                self.assertEqual(resolve_model_alias(fm["advisor"]), STRONG,
                                 f"{role} advisor alias 'strong' must resolve to {STRONG} "
                                 f"(intentional delta: was claude-opus-4-7 pre-migration)")


# ---------------------------------------------------------------------------
# Batch C — Sonnet exec, advisor `none` → `mid`
# ---------------------------------------------------------------------------

class BatchCSonnetAdvisorNoneCards(unittest.TestCase):
    def test_batch_c_sonnet_advisor_none_cards(self):
        from model_alias import resolve_model_alias
        for role in ("database-engineer", "product-reviewer", "qa-engineer"):
            with self.subTest(role=role):
                fm, _ = _frontmatter(role)
                self.assertEqual(fm["executor"], "mid",
                                 f"{role} executor must be alias 'mid'")
                self.assertEqual(resolve_model_alias(fm["executor"]), MID,
                                 f"alias 'mid' must resolve to {MID}")
                self.assertEqual(fm["advisor"], "none",
                                 f"{role} advisor must remain literal 'none'")


# ---------------------------------------------------------------------------
# Batch D — Haiku executors → `cheap`
# ---------------------------------------------------------------------------

class BatchDHaikuCards(unittest.TestCase):
    def test_batch_d_haiku_cards_resolve_cheap(self):
        from model_alias import resolve_model_alias
        for role in ("architect-context-recon", "planning-agent",
                     "session-memory-updater", "plan-cache-adapter"):
            with self.subTest(role=role):
                fm, _ = _frontmatter(role)
                self.assertEqual(fm["executor"], "cheap",
                                 f"{role} executor must be alias 'cheap'")
                self.assertEqual(resolve_model_alias(fm["executor"]), CHEAP,
                                 f"alias 'cheap' must resolve to {CHEAP} "
                                 f"(plan-cache-adapter: intentional canonicalization "
                                 f"bare haiku-4-5 → datestamped)")


# ---------------------------------------------------------------------------
# Batch E — executor_resolver.py force-opus path via alias
# ---------------------------------------------------------------------------

class BatchEExecutorResolver(unittest.TestCase):
    def test_executor_resolver_force_opus_resolves_via_alias(self):
        from model_alias import resolve_model_alias
        from executor_resolver import resolve_executor
        env = {"CLAUDE_FORCE_OPUS": "1"}
        fm = {"executor": "mid"}
        result = resolve_executor("software-engineer", env, fm)
        self.assertEqual(result, resolve_model_alias("strong"),
                         "force-opus path must resolve via alias 'strong' → "
                         f"{STRONG} (intentional delta: was claude-opus-4-7 pre-migration)")


# ---------------------------------------------------------------------------
# Batch D/E — AC-D3 final sweep
# ---------------------------------------------------------------------------

class FinalSweepNoHardcodes(unittest.TestCase):
    def test_no_hardcoded_opus_4_7_anywhere_in_scope(self):
        """No agent card executor/advisor holds a claude-* literal (except 'none').

        Also: executor_resolver.py source+docstring must not contain claude-opus-4-7.
        Scope: only executor_resolver.py, not the whole repo (test files legitimately
        contain the literal as passthrough-proof assertions).
        """
        agent_files = sorted(AGENTS_DIR.glob("*.md"))
        for path in agent_files:
            text = path.read_text()
            match = re.match(r"^---\n(.*?)\n---", text, re.DOTALL)
            if not match:
                continue
            fm = yaml.safe_load(match.group(1)) or {}
            for field in ("executor", "advisor"):
                value = fm.get(field, "")
                if value == "none":
                    continue
                self.assertFalse(
                    isinstance(value, str) and value.startswith("claude-"),
                    f"{path.name} {field}: still holds a concrete claude-* literal "
                    f"({value!r}); must be a logical alias",
                )
        resolver_path = REPO_ROOT / "hooks" / "_lib" / "executor_resolver.py"
        resolver_text = resolver_path.read_text()
        self.assertNotIn(
            "claude-opus-4-7",
            resolver_text,
            "hooks/_lib/executor_resolver.py must not contain 'claude-opus-4-7' "
            "(source or docstring); use resolve_model_alias('strong') instead",
        )
