"""Slice 11: regression guard for S5.1 invariants.

Guards that future changes do not silently undo S5.1 commitments:
1. download-model.sh must document UNHEALTHY recovery path (delete + re-run).
2. download-model.sh must no longer claim the model is "not consumed".
3. SKILL.md must no longer carry the infrastructure-only banner.
4. real.py must exist and export a `build()` factory (not a NotImplementedError stub).
5. Fake embedder banner must still warn against production use.
"""
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
_SCRIPT = REPO_ROOT / "skills" / "embedder" / "download-model.sh"
_SKILL_MD = REPO_ROOT / "skills" / "embedder" / "SKILL.md"
_REAL_PY = REPO_ROOT / "skills" / "embedder" / "_lib" / "real.py"


class DownloadScriptGuidesUnhealthyRecovery(unittest.TestCase):
    def test_script_mentions_unhealthy_doctor_recovery(self):
        body = _SCRIPT.read_text()
        self.assertIn("UNHEALTHY", body)
        self.assertIn("delete", body.lower())
        self.assertIn("re-run", body.lower())


class DownloadScriptDropsS5Deferral(unittest.TestCase):
    def test_script_no_longer_claims_model_is_unused(self):
        body = _SCRIPT.read_text()
        self.assertNotIn("does NOT consume", body)
        self.assertNotIn("not yet implemented", body)


class SkillMarkdownDropsInfrastructureBanner(unittest.TestCase):
    def test_skill_md_has_no_infrastructure_only_banner(self):
        text = _SKILL_MD.read_text()
        self.assertNotIn("infrastructure only", text)


class RealEmbedderBuildFactoryExists(unittest.TestCase):
    def test_real_py_exports_build_callable(self):
        _ensure_skill_on_path()
        from embedder._lib import real
        self.assertTrue(callable(getattr(real, "build", None)))


class FakeEmbedderBannerWarnsProduction(unittest.TestCase):
    def test_skill_md_still_warns_fake_is_not_production(self):
        text = _SKILL_MD.read_text()
        self.assertIn("Do not use in", text)
        self.assertIn("production", text)


def _ensure_skill_on_path():
    skill = str(REPO_ROOT / "skills")
    if skill not in sys.path:
        sys.path.insert(0, skill)


if __name__ == "__main__":
    unittest.main()
