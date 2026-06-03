"""Slice A' AC2: settings.json hook entries are in exec-form.

After the v2.1.139 exec-form sweep, every `hooks.<EVENT>[].hooks[]` entry
where `type == "command"` MUST split the shell tokens into:
  - `command`: the binary to invoke (str)
  - `args`: a list of string arguments (list[str])

Three sub-forms exist:
  - **Bash-wrapped** (76 entries): `command="bash"` + `args=["${PATH}/hook.sh"]`
  - **hcom subcmd** (10 entries): `command="…/hcom"` + `args=[<subcmd>]`
  - **Inline shell** (6 entries): `command="bash"` + `args=["-c", "<pipeline>"]`

Two typed sibling entries (`type == "mcp_tool"` and `type == "agent"`) live
under `hooks` and retain their own structured schemas — they are NOT in
scope and must not gain a spurious `args` key.

The `mcpServers` block lives OUTSIDE `hooks` and is verified separately as
a regression guard (it was already exec-form before this sweep).

These tests freeze the v2.1.139 schema. If a future edit reverts to
string-form `"command": "bash foo.sh"` they will fire — that is desired.
"""
import json
import re
import unittest
from pathlib import Path

from tests._helpers.settings_hook import is_script_path

REPO_ROOT = Path(__file__).resolve().parents[1]
SETTINGS_PATH = REPO_ROOT / "settings.json"


def _command_entries():
    """Yield every (event, matcher_idx, hook_idx, hook_dict) under hooks.<EVENT>[].hooks[]."""
    data = json.loads(SETTINGS_PATH.read_text())
    hooks = data.get("hooks", {})
    for event, matchers in hooks.items():
        for m_idx, matcher in enumerate(matchers):
            for h_idx, hook in enumerate(matcher.get("hooks", [])):
                yield (event, m_idx, h_idx, hook)


def _command_type_entries():
    """Yield only entries with type == 'command'."""
    for event, m_idx, h_idx, hook in _command_entries():
        if hook.get("type") == "command":
            yield (event, m_idx, h_idx, hook)


def _tag(event, m_idx, h_idx):
    return f"hooks.{event}[{m_idx}].hooks[{h_idx}]"


class EveryCommandHookHasExecFormArgs(unittest.TestCase):
    def test_every_command_type_hook_entry_has_args_list(self):
        for event, m_idx, h_idx, hook in _command_type_entries():
            tag = _tag(event, m_idx, h_idx)
            self.assertIn("command", hook, f"{tag}: missing `command` key")
            self.assertIsInstance(
                hook["command"], str,
                f"{tag}: `command` must be str, got {type(hook['command']).__name__}"
            )
            self.assertIn("args", hook, f"{tag}: missing `args` key (exec-form required)")
            self.assertIsInstance(
                hook["args"], list,
                f"{tag}: `args` must be list, got {type(hook['args']).__name__}"
            )
            for i, a in enumerate(hook["args"]):
                self.assertIsInstance(
                    a, str,
                    f"{tag}: args[{i}] must be str, got {type(a).__name__}"
                )


class NoBashDashCStringFormSurvives(unittest.TestCase):
    def test_no_command_string_contains_bash_dash_c_literal(self):
        for event, m_idx, h_idx, hook in _command_type_entries():
            tag = _tag(event, m_idx, h_idx)
            self.assertNotIn(
                "bash -c ", hook["command"],
                f"{tag}: `command` field still contains `bash -c ` literal "
                f"(only acceptable inside args[1] for inline-shell entries)"
            )


class HcomSubcmdSplit(unittest.TestCase):
    SUBCMD_RE = re.compile(r"^[a-z][a-z0-9-]*$")

    def test_hcom_entries_split_binary_and_subcmd(self):
        hcom_entries = [
            (event, m_idx, h_idx, hook)
            for event, m_idx, h_idx, hook in _command_type_entries()
            if "/hcom" in hook["command"] or hook["command"].endswith("hcom")
        ]
        self.assertGreater(
            len(hcom_entries), 0,
            "no hcom entries found — enumeration changed?"
        )
        for event, m_idx, h_idx, hook in hcom_entries:
            tag = _tag(event, m_idx, h_idx)
            self.assertTrue(
                hook["command"].endswith("/hcom") or hook["command"].endswith("hcom"),
                f"{tag}: command must end with `hcom` (no trailing subcmd), got {hook['command']!r}"
            )
            self.assertGreaterEqual(
                len(hook["args"]), 1,
                f"{tag}: hcom entry must have at least one arg (the subcommand)"
            )
            sub = hook["args"][0]
            self.assertTrue(
                self.SUBCMD_RE.match(sub),
                f"{tag}: args[0]={sub!r} must match {self.SUBCMD_RE.pattern}"
            )


class InlineShellEntriesUseBashDashC(unittest.TestCase):
    """Inline-shell entries (originally `bash <pipeline>` string-form) MUST split
    to `command='bash'` + `args=['-c', '<pipeline>']`. A bash entry whose
    args[0] is NEITHER a script path (ends in `.sh`) NOR `-c` is malformed —
    it would mean a shell pipeline was passed as bash's positional arg, which
    silently fails at runtime (bash would treat the pipeline as a $0 script).
    """

    def test_inline_shell_entries_use_explicit_bash_dash_c(self):
        bash_entries = [
            (event, m_idx, h_idx, hook)
            for event, m_idx, h_idx, hook in _command_type_entries()
            if hook.get("command") == "bash"
        ]
        # Partition into script-form (args[0] looks like a path) vs inline-form (everything else).
        # Inline-form must use the explicit `-c` flag.
        inline_entries = [
            (event, m_idx, h_idx, hook)
            for event, m_idx, h_idx, hook in bash_entries
            if not (hook.get("args") and is_script_path(hook["args"][0]))
        ]
        self.assertGreater(
            len(inline_entries), 0,
            "no inline-shell entries found — enumeration changed?"
        )
        for event, m_idx, h_idx, hook in inline_entries:
            tag = _tag(event, m_idx, h_idx)
            self.assertGreaterEqual(
                len(hook["args"]), 2,
                f"{tag}: inline-shell entries must have at least 2 args (-c + pipeline)"
            )
            self.assertEqual(
                hook["args"][0], "-c",
                f"{tag}: inline-shell entry args[0] must be '-c' (got {hook['args'][0]!r}); "
                f"otherwise bash treats args[1] as $0 and the pipeline silently no-ops"
            )
            self.assertGreater(
                len(hook["args"][1]), 0,
                f"{tag}: inline-shell args[1] (the shell pipeline) must be non-empty"
            )


class TypedEntriesUnchanged(unittest.TestCase):
    """`type ∈ {mcp_tool, agent}` entries under hooks retain their typed schema."""

    def test_typed_entries_preserve_structured_shape(self):
        typed = [
            (event, m_idx, h_idx, hook)
            for event, m_idx, h_idx, hook in _command_entries()
            if hook.get("type") in ("mcp_tool", "agent")
        ]
        self.assertGreater(
            len(typed), 0,
            "no typed (mcp_tool/agent) entries found — enumeration changed?"
        )
        for event, m_idx, h_idx, hook in typed:
            tag = _tag(event, m_idx, h_idx)
            t = hook["type"]
            self.assertNotIn(
                "args", hook,
                f"{tag}: typed entry (type={t}) must NOT carry a spurious `args` key"
            )
            self.assertNotIn(
                "command", hook,
                f"{tag}: typed entry (type={t}) must NOT carry a `command` key"
            )
            if t == "mcp_tool":
                for required in ("server", "tool"):
                    self.assertIn(
                        required, hook,
                        f"{tag}: mcp_tool entry must declare `{required}`"
                    )
            elif t == "agent":
                self.assertIn(
                    "prompt", hook,
                    f"{tag}: agent entry must declare `prompt`"
                )


class McpServersUntouched(unittest.TestCase):
    EXPECTED_SERVERS = {"memory", "gh-cache", "lsp-typescript", "lsp-pyright"}

    def test_mcpServers_block_unchanged(self):
        data = json.loads(SETTINGS_PATH.read_text())
        self.assertIn(
            "mcpServers", data,
            "settings.json must retain top-level mcpServers block"
        )
        servers = data["mcpServers"]
        self.assertIsInstance(servers, dict)
        self.assertEqual(
            set(servers.keys()), self.EXPECTED_SERVERS,
            f"mcpServers keys changed; expected {self.EXPECTED_SERVERS}, got {set(servers.keys())}"
        )
        for name, server in servers.items():
            self.assertEqual(
                server.get("command"), "bash",
                f"mcpServers[{name}] must already be exec-form (command='bash')"
            )
            self.assertIsInstance(
                server.get("args"), list,
                f"mcpServers[{name}] must already be exec-form (args=list)"
            )


class ThreeTierFallbackPresent(unittest.TestCase):
    """AC-A4a/b: hook entry-points use three-tier CLAUDE_PLUGIN_ROOT fallback."""

    TWO_TIER = re.compile(r'\$\{CLAUDE_CONFIG_DIR:-\$HOME/\.claude\}/hooks/')
    THREE_TIER = "${CLAUDE_PLUGIN_ROOT:-${CLAUDE_CONFIG_DIR:-$HOME/.claude}}/hooks/"

    def test_settings_json_valid_after_sweep(self):
        text = SETTINGS_PATH.read_text()
        json.loads(text)  # raises json.JSONDecodeError on invalid JSON

    def test_hook_commands_use_three_tier_fallback(self):
        text = SETTINGS_PATH.read_text()
        self.assertFalse(
            self.TWO_TIER.search(text),
            "settings.json still has two-tier ${CLAUDE_CONFIG_DIR:-$HOME/.claude}/hooks/ patterns",
        )
        self.assertIn(
            self.THREE_TIER, text,
            "settings.json has no three-tier CLAUDE_PLUGIN_ROOT hook entry-points",
        )


if __name__ == "__main__":
    unittest.main()
