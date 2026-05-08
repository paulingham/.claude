"""C-AC9: snapshot-fixture test asserting `hooks/pre-agent-thinking.sh` is
NOT modified by Slice C of the opus47-adapt pipeline.

The fixture is the SHA-256 captured at the start of the slice (pre-build).
Any later commit that mutates the file will fail this test, regardless of
whether the mutation appears intentional. Restoring the file's content (or
acknowledging an intended change in a follow-up slice) is required to
unblock CI.

Promotion of the hook to enforcement (Path A silent injection or hard-block
Path B) when Claude Code exposes the `thinking` field is a future,
explicitly-scoped slice — at which point this fixture is updated.
"""
import hashlib
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SHIM_PATH = REPO_ROOT / "hooks" / "pre-agent-thinking.sh"

# Snapshot fixture captured at the start of Slice C build (pre-edit state of
# the shim). See pipeline-state/opus47-adapt/plan.md § Slice C, C-AC9.
PRE_BUILD_SHA256 = (
    "a2e992d0457e2eef075cebef687d88e844d71aa0feffed6e863c38654f72e12e"
)


class HookShimUnchanged(unittest.TestCase):
    def test_pre_agent_thinking_sh_not_modified(self):
        actual = hashlib.sha256(SHIM_PATH.read_bytes()).hexdigest()
        self.assertEqual(
            actual,
            PRE_BUILD_SHA256,
            (
                f"hooks/pre-agent-thinking.sh content has changed since the "
                f"Slice C pre-build snapshot.\n"
                f"  expected sha256: {PRE_BUILD_SHA256}\n"
                f"  actual   sha256: {actual}\n"
                f"Slice C of opus47-adapt MUST NOT modify the bash shim "
                f"(C-AC9). Promotion to enforcement is an explicit future "
                f"slice; until then, the shim is invariant."
            ),
        )


if __name__ == "__main__":
    unittest.main()
