"""Drift test: hook source-loading paths and settings.json hook commands
must use ${CLAUDE_CONFIG_DIR:-$HOME/.claude}, never bare ~/.claude or $HOME/.claude.

Without this gate, the harness silently fails on any environment where
$HOME does not equal the actual config directory (Claude Code on the web
sandbox, NFS-mounted homedirs, container shells with non-default $HOME,
corp-managed dotfiles via stow, etc.).

This test pins the convention so a future hook author cannot reintroduce
the bare-tilde pattern without a deliberate test update.
"""
import json
import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

# Source-line patterns that load config-side bash files. These MUST go through
# CLAUDE_CONFIG_DIR for portability. Bare `~/.claude/` and bare `$HOME/.claude/`
# expand against $HOME, which breaks when the config dir lives elsewhere.
_BARE_SOURCE_LINE = re.compile(
    r"^[ \t]*source[ \t]+(~/\.claude/|\"\$HOME/\.claude/)",
    re.MULTILINE,
)

# Settings.json command-string patterns that invoke a config-tree hook.
# `bash ~/.claude/hooks/X.sh` and `bash "$HOME/.claude/hooks/X.sh"` are both
# bare patterns. The portable form is `bash "${CLAUDE_CONFIG_DIR:-$HOME/.claude}/hooks/X.sh"`.
_BARE_HOOK_COMMAND = re.compile(
    r"bash\s+(~/\.claude/hooks/|\"\$HOME/\.claude/hooks/)",
)


def _bash_files():
    yield from (REPO_ROOT / "hooks").glob("*.sh")
    yield from (REPO_ROOT / "hooks" / "_lib").glob("*.sh")


class HookSourceLinesUseConfigDirIndirection(unittest.TestCase):
    def test_no_bare_tilde_or_home_in_source_lines(self):
        offenders = []
        for path in _bash_files():
            text = path.read_text()
            for line_no, line in enumerate(text.splitlines(), start=1):
                if _BARE_SOURCE_LINE.search(line):
                    offenders.append(f"{path.relative_to(REPO_ROOT)}:{line_no}: {line.strip()}")
        self.assertEqual(
            offenders, [],
            "Hook scripts must use ${CLAUDE_CONFIG_DIR:-$HOME/.claude}/... in "
            "`source` lines, not bare `~/.claude/` or `$HOME/.claude/`. "
            "Drift: " + "; ".join(offenders))


class SettingsJsonHookCommandsUseConfigDirIndirection(unittest.TestCase):
    def test_no_bare_tilde_or_home_in_hook_commands(self):
        settings = json.loads((REPO_ROOT / "settings.json").read_text())
        offenders = []
        for hook_event, blocks in settings.get("hooks", {}).items():
            for block in blocks:
                for hook in block.get("hooks", []):
                    cmd = hook.get("command", "")
                    if _BARE_HOOK_COMMAND.search(cmd):
                        offenders.append(f"{hook_event}: {cmd}")
        self.assertEqual(
            offenders, [],
            "settings.json hook commands must use "
            "${CLAUDE_CONFIG_DIR:-$HOME/.claude}/... not bare "
            "~/.claude/ or $HOME/.claude/. Drift: " + "; ".join(offenders))


if __name__ == "__main__":
    unittest.main()
