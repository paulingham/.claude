"""ATDD tests — `hooks/_lib/pr_cost_annotate.py`.

Covers the five contract assertions from the plan:
1. formatter: known usage_by_model -> correct $X.XX total + per-model breakdown
2. targeted replace / no-clobber: only the sentinel line changes
3. idempotent: replace twice -> identical body, exactly one cost line
4. fail-open: bad transcript path -> graceful, exit 0, never raises
5. sentinel-absent append-once: appends exactly one cost line

Imports are via conftest.py (hooks/_lib on sys.path) so no per-file path hack.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

# WHY: conftest.py prepends hooks/_lib — just import directly.
import pr_cost_annotate
from pr_cost_annotate import format_cost_line, replace_sentinel, resolve_live_transcript
from cost_estimator import estimate_cost_usd

REPO_ROOT = Path(__file__).resolve().parent.parent
HOOKS_LIB = REPO_ROOT / "hooks" / "_lib"


class FormatterKnownUsage(unittest.TestCase):
    """1. formatter: known usage_by_model -> correct $X.XX + per-model breakdown."""

    def _opus_usage(self):
        return {
            "input_tokens": 1_000_000,
            "output_tokens": 0,
            "cache_read_input_tokens": 0,
            "cache_creation_input_tokens": 0,
        }

    def _sonnet_usage(self):
        return {
            "input_tokens": 1_000_000,
            "output_tokens": 0,
            "cache_read_input_tokens": 0,
            "cache_creation_input_tokens": 0,
        }

    def test_format_cost_line_starts_with_sentinel_prefix(self):
        usage = {"claude-opus-4-8": self._opus_usage()}
        line = format_cost_line(usage)
        self.assertTrue(
            line.startswith("**Pipeline cost:**"),
            msg=f"expected sentinel prefix, got: {line!r}",
        )

    def test_format_cost_line_total_matches_estimate_cost_usd(self):
        """Total in the formatted line must match estimate_cost_usd cross-check."""
        opus_usage = self._opus_usage()
        usage_by_model = {"claude-opus-4-8": opus_usage}
        # cross-check: estimate_cost_usd takes list of records
        record = {"model": "claude-opus-4-8", **opus_usage}
        expected = estimate_cost_usd([record])
        line = format_cost_line(usage_by_model)
        # line must contain the expected dollar amount formatted to 2dp
        self.assertIn(
            f"${expected:.2f}",
            line,
            msg=f"formatted line must contain expected total ${expected:.2f}: {line!r}",
        )

    def test_format_cost_line_per_model_breakdown_present(self):
        """Line must include a per-model breakdown in parentheses."""
        usage = {
            "claude-opus-4-8": self._opus_usage(),
            "claude-sonnet-4-6": self._sonnet_usage(),
        }
        line = format_cost_line(usage)
        self.assertIn("claude-opus-4-8", line)
        self.assertIn("claude-sonnet-4-6", line)
        # breakdown is in parentheses
        self.assertIn("(", line)
        self.assertIn(")", line)

    def test_format_cost_line_zero_usage_shows_zero_dollars(self):
        """$0 usage -> $0.00."""
        line = format_cost_line({})
        self.assertIn("$0.00", line, msg=f"zero usage must show $0.00: {line!r}")

    def test_format_cost_line_multi_model_total_is_sum(self):
        """Multi-model total = sum of individual costs."""
        opus_rec = {"model": "claude-opus-4-8", **self._opus_usage()}
        sonnet_rec = {"model": "claude-sonnet-4-6", **self._sonnet_usage()}
        expected = estimate_cost_usd([opus_rec, sonnet_rec])
        usage = {
            "claude-opus-4-8": self._opus_usage(),
            "claude-sonnet-4-6": self._sonnet_usage(),
        }
        line = format_cost_line(usage)
        self.assertIn(f"${expected:.2f}", line)


class ReplaceSentinelNoClobber(unittest.TestCase):
    """2. targeted replace / no-clobber: only the sentinel line changes."""

    _PROSE = (
        "## Summary\n"
        "This PR fixes a bug in the widget factory.\n"
        "\n"
        "**Changes:**\n"
        "- Rewrote widget.py\n"
        "- Added tests\n"
    )
    _SENTINEL = "**Pipeline cost:** _pending CI_\n"

    def _body_with_sentinel(self):
        return self._PROSE + self._SENTINEL

    def test_replace_only_cost_line_changes(self):
        """Every prose line must be byte-identical after replace."""
        body = self._body_with_sentinel()
        new_line = "**Pipeline cost:** $5.00 (claude-opus-4-8 $5.00)"
        result = replace_sentinel(body, new_line)

        prose_before = self._PROSE.splitlines(keepends=True)
        prose_after = result.splitlines(keepends=True)[: len(prose_before)]
        self.assertEqual(
            prose_before,
            prose_after,
            msg="replace_sentinel must not modify any non-sentinel lines",
        )

    def test_replace_produces_new_cost_line(self):
        body = self._body_with_sentinel()
        new_line = "**Pipeline cost:** $3.00 (claude-sonnet-4-6 $3.00)"
        result = replace_sentinel(body, new_line)
        self.assertIn(new_line, result)
        self.assertNotIn("_pending CI_", result)


class ReplaceSentinelIdempotent(unittest.TestCase):
    """3. idempotent: replace twice -> identical body, exactly one cost line."""

    def test_replace_twice_identical_body(self):
        body = "Some prose.\n**Pipeline cost:** _pending CI_\nMore prose.\n"
        new_line = "**Pipeline cost:** $2.50 (haiku $0.50, opus $2.00)"
        once = replace_sentinel(body, new_line)
        twice = replace_sentinel(once, new_line)
        self.assertEqual(once, twice, msg="replace_sentinel must be idempotent")

    def test_replace_twice_exactly_one_cost_line(self):
        body = "Header.\n**Pipeline cost:** _pending CI_\nFooter.\n"
        new_line = "**Pipeline cost:** $1.00"
        twice = replace_sentinel(replace_sentinel(body, new_line), new_line)
        count = twice.count("**Pipeline cost:**")
        self.assertEqual(
            count,
            1,
            msg=f"exactly one cost line expected after two replaces, got {count}",
        )

    def test_replace_different_new_lines_updates_to_latest(self):
        """Calling replace twice with different values -> last value wins."""
        body = "Text.\n**Pipeline cost:** _pending CI_\n"
        first = replace_sentinel(body, "**Pipeline cost:** $1.00")
        second = replace_sentinel(first, "**Pipeline cost:** $2.00")
        self.assertIn("$2.00", second)
        self.assertNotIn("$1.00", second)


class FailOpenBadTranscript(unittest.TestCase):
    """4. fail-open: bad/missing transcript -> graceful, exit 0, never raises."""

    def test_resolve_live_transcript_missing_dir_returns_none(self):
        result = resolve_live_transcript(
            projects_root="/nonexistent/path/does/not/exist",
            cwd_slug="fake-slug",
        )
        self.assertIsNone(result)

    def test_resolve_live_transcript_empty_dir_returns_none(self, tmp_path=None):
        """Dir with no *.jsonl files -> None."""
        with tempfile.TemporaryDirectory() as tmpd:
            cwd_slug = "my-project"
            slug_dir = Path(tmpd) / cwd_slug
            slug_dir.mkdir()
            result = resolve_live_transcript(
                projects_root=tmpd,
                cwd_slug=cwd_slug,
            )
            self.assertIsNone(result)

    def test_main_with_bad_transcript_exits_zero(self):
        """CLI main with --transcript pointing to a nonexistent file exits 0."""
        script = str(HOOKS_LIB / "pr_cost_annotate.py")
        env = {**os.environ, "PYTHONPATH": str(HOOKS_LIB)}
        # Use a fake PR number and fake transcript path — gh will fail (no auth
        # in CI / no real PR); the bare-except must catch all and exit 0.
        result = subprocess.run(
            [sys.executable, script, "0", "--transcript", "/dev/null/does_not_exist"],
            capture_output=True,
            text=True,
            env=env,
        )
        self.assertEqual(
            result.returncode,
            0,
            msg=(
                f"pr_cost_annotate must exit 0 on bad transcript. "
                f"Got rc={result.returncode}. stderr: {result.stderr!r}"
            ),
        )

    def test_format_cost_line_never_raises_on_empty_usage(self):
        """format_cost_line with {} must not raise."""
        try:
            line = format_cost_line({})
        except Exception as exc:
            self.fail(f"format_cost_line({{}}) raised {exc!r}")
        self.assertIsInstance(line, str)


class SentinelAbsentAppendOnce(unittest.TestCase):
    """5. sentinel-absent append-once: body with no sentinel -> exactly one line appended."""

    def test_append_when_absent(self):
        body = "No cost line here.\nJust prose.\n"
        new_line = "**Pipeline cost:** $4.20"
        result = replace_sentinel(body, new_line)
        self.assertIn(new_line, result)

    def test_appended_exactly_once(self):
        body = "Just prose, no sentinel."
        new_line = "**Pipeline cost:** $0.01"
        result = replace_sentinel(body, new_line)
        count = result.count("**Pipeline cost:**")
        self.assertEqual(count, 1, msg=f"expected exactly 1 cost line, got {count}")

    def test_existing_prose_preserved_on_append(self):
        body = "Header prose.\nSome details.\n"
        new_line = "**Pipeline cost:** $7.00"
        result = replace_sentinel(body, new_line)
        self.assertIn("Header prose.", result)
        self.assertIn("Some details.", result)



class SlugDerivation(unittest.TestCase):
    """6. slug: _cwd_slug replaces both / and . with -, preserving leading dash."""

    def test_known_path_matches_real_projects_dir(self):
        """/Users/Paul.Ingham/Projects/.claude -> -Users-Paul-Ingham-Projects--claude."""
        import unittest.mock as mock
        with mock.patch("os.getcwd", return_value="/Users/Paul.Ingham/Projects/.claude"):
            slug = pr_cost_annotate._cwd_slug()
        self.assertEqual(
            slug,
            "-Users-Paul-Ingham-Projects--claude",
            msg=f"got {slug!r} — expected dots AND slashes replaced, leading dash kept",
        )

    def test_simple_path_no_dots(self):
        """Path with no dots: only slashes replaced, leading dash preserved."""
        import unittest.mock as mock
        with mock.patch("os.getcwd", return_value="/home/user/myproject"):
            slug = pr_cost_annotate._cwd_slug()
        self.assertEqual(slug, "-home-user-myproject")

    def test_path_with_dot_segment(self):
        """Path with a dotfile segment (.config) gets double dash."""
        import unittest.mock as mock
        with mock.patch("os.getcwd", return_value="/home/user/.config/myapp"):
            slug = pr_cost_annotate._cwd_slug()
        self.assertEqual(slug, "-home-user--config-myapp")

    def test_leading_dash_kept(self):
        """Leading dash must NOT be stripped — real projects dir slug starts with -."""
        import unittest.mock as mock
        with mock.patch("os.getcwd", return_value="/any/path"):
            slug = pr_cost_annotate._cwd_slug()
        self.assertTrue(
            slug.startswith("-"),
            msg=f"slug must keep leading dash, got {slug!r}",
        )


class ResolveTranscriptSlugIntegration(unittest.TestCase):
    """7. resolve_live_transcript with real slug shape picks newest top-level jsonl."""

    def test_picks_newest_top_level_jsonl(self):
        """Given a slug dir with two jsonl files, the newest is returned."""
        import time
        with tempfile.TemporaryDirectory() as tmpd:
            slug = "-Users-Paul-Ingham-Projects--claude"
            slug_dir = Path(tmpd) / slug
            slug_dir.mkdir()
            old = slug_dir / "session-old.jsonl"
            new = slug_dir / "session-new.jsonl"
            old.write_text("{}")
            time.sleep(0.05)
            new.write_text("{}")
            result = resolve_live_transcript(tmpd, slug)
            self.assertEqual(
                Path(result).name,
                "session-new.jsonl",
                msg=f"expected newest file, got {result!r}",
            )

    def test_excludes_subagents_dir(self):
        """jsonl files inside subagents/ must not be candidates."""
        with tempfile.TemporaryDirectory() as tmpd:
            slug = "-Users-Paul-Ingham-Projects--claude"
            slug_dir = Path(tmpd) / slug
            subagents_dir = slug_dir / "subagents"
            subagents_dir.mkdir(parents=True)
            top = slug_dir / "main-session.jsonl"
            nested = subagents_dir / "nested.jsonl"
            top.write_text("{}")
            nested.write_text("{}")
            result = resolve_live_transcript(tmpd, slug)
            self.assertIsNotNone(result)
            self.assertNotIn(
                "subagents",
                result,
                msg=f"subagents jsonl must be excluded, got {result!r}",
            )
            self.assertEqual(Path(result).name, "main-session.jsonl")

    def test_only_subagents_jsonl_returns_none(self):
        """If only subagents/ jsonl exists (no top-level), returns None."""
        with tempfile.TemporaryDirectory() as tmpd:
            slug = "-Users-Paul-Ingham-Projects--claude"
            slug_dir = Path(tmpd) / slug
            subagents_dir = slug_dir / "subagents"
            subagents_dir.mkdir(parents=True)
            (subagents_dir / "sub.jsonl").write_text("{}")
            result = resolve_live_transcript(tmpd, slug)
            self.assertIsNone(
                result,
                msg="only subagents jsonl must yield None from resolve_live_transcript",
            )

if __name__ == "__main__":
    unittest.main()
