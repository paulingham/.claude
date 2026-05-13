"""Test helpers for parsing settings.json hook entries in the v2.1.140 exec-form schema (command + args).

The v2.1.139 sweep split every `type == "command"` hook entry from string-form
`"command": "bash foo.sh"` into exec-form `command="bash" + args=["foo.sh"]`.
Tests that substring-match on a script basename must inspect both fields,
which is what `effective_command_line` reconstructs.
"""


def effective_command_line(hook: dict) -> str:
    """Reconstruct an effective shell command line from a hook entry.

    v2.1.139 split string-form `bash foo.sh` into exec-form
    `command=bash`, `args=[foo.sh]`. Tests that substring-match on the
    script basename must inspect both fields. Returns "" for non-command
    typed entries (mcp_tool, agent).
    """
    if hook.get("type") != "command":
        return ""
    cmd = hook.get("command", "")
    args = hook.get("args", []) or []
    return " ".join([cmd, *args]).strip()


def is_script_path(arg: str) -> bool:
    """True when an args[0] entry refers to a script path rather than `-c`.

    A bash hook entry whose args[0] ends in `.sh` is the script-form
    (originally `bash /path/to/hook.sh`); anything else is the inline-shell
    form which MUST use `-c` per the v2.1.140 schema. Used by the schema
    freeze test to partition bash entries into script-form vs inline-form.
    """
    return arg.endswith(".sh") or arg.endswith(".sh\"") or ".sh\"" in arg
