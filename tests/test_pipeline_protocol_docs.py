"""Slice 3 AC10 — pipeline-protocol.md and pipeline-rigour.md document PDR-RTV.

`protocols/pipeline-protocol.md` § Build Phase Dispatch Variants
documents the routing precedence (`pdr_rtv > bestofn > standard`).
`rules/pipeline-rigour.md` § Pipeline Phase Order summary mentions PDR-RTV as
a Build dispatch variant (this section moved out of rules/core.md, which is
now a thin @-include index, in the Phase B gear-tier split).
"""
import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
PIPELINE_PROTOCOL_DETAIL = (
    REPO_ROOT / "protocols" / "pipeline-protocol.md")
CORE_RULES = REPO_ROOT / "rules" / "pipeline-rigour.md"


class BuildDispatchVariantsDocumentsPdrRtv(unittest.TestCase):
    def test_pipeline_protocol_documents_build_dispatch_variants(self):
        content = PIPELINE_PROTOCOL_DETAIL.read_text()
        self.assertIn(
            "Build Phase Dispatch Variants", content,
            "protocols/pipeline-protocol.md must contain a "
            "'Build Phase Dispatch Variants' subsection")

    def test_pipeline_protocol_documents_routing_precedence(self):
        content = PIPELINE_PROTOCOL_DETAIL.read_text()
        # Routing order: pdr_rtv > bestofn > standard.
        # Match the literal precedence chain in any of the standard
        # forms: pdr_rtv > bestofn, or pdr_rtv before bestofn in prose.
        self.assertRegex(
            content,
            r"pdr_rtv\s*>\s*bestofn\s*>\s*standard",
            msg="pipeline-protocol.md must document the precedence "
                "chain `pdr_rtv > bestofn > standard`")

    def test_pipeline_protocol_mentions_pdr_rtv_dispatch(self):
        content = PIPELINE_PROTOCOL_DETAIL.read_text()
        # The Build Phase Dispatch Variants section must reference the
        # /pdr-rtv skill and Best-of-N composition.
        self.assertIn("pdr-rtv", content.lower())
        self.assertIn("bestofn", content.lower())

    def test_core_rules_mentions_pdr_rtv_as_build_variant(self):
        content = CORE_RULES.read_text()
        # § Pipeline Phase Order summary must reference PDR-RTV as a
        # Build dispatch variant.
        match = re.search(
            r"##\s+Pipeline Phase Order(.+?)(?=^##\s+|\Z)",
            content, re.DOTALL | re.MULTILINE)
        self.assertIsNotNone(
            match,
            "rules/pipeline-rigour.md must contain '## Pipeline Phase Order' section")
        section = match.group(1)
        self.assertIn(
            "PDR-RTV", section,
            "Pipeline Phase Order section must mention PDR-RTV as a "
            "Build dispatch variant")


if __name__ == "__main__":
    unittest.main()
