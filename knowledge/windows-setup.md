# Windows Setup for the Claude Code Harness

The harness requires **bash**, a **Python interpreter**, and **git** to be present
in the shell that Claude Code uses. On Windows, these are not available by default.
`hooks/harness-dependency-gate.sh` ENFORCES these prerequisites — it blocks Agent
spawns (exit 2) until bash + a Python interpreter + git are present in the PATH.
Set `CLAUDE_DISABLE_DEPENDENCY_GATE=1` to override the gate temporarily.

## Required Prerequisites

### 1. Git for Windows (provides bash + git)

**Install via winget (recommended):**

```powershell
winget install Git.Git
```

**Direct download (fallback):** https://git-scm.com/download/win

During installation, accept the default option to add Git to PATH. This also
installs Git Bash at `C:\Program Files\Git\bin\bash.exe`.

### 2. Python Interpreter

**Install via winget (recommended):**

```powershell
winget install Python.Python.3.12
```

**Direct download (fallback):** https://www.python.org/downloads/windows/

During installation, check **"Add Python to PATH"**.

> **Note:** On Windows the interpreter is `python` or `py`, not `python3`.
> The harness dependency probe checks all three (`python3`, `python`, `py`)
> so any of the three resolving in PATH satisfies the gate.

## Configure Claude Code to Use Git Bash

Claude Code must be pointed at Git Bash so the harness hook scripts run under
a POSIX-compatible shell. Add the following to your `settings.json`:

```json
{"env":{"CLAUDE_CODE_GIT_BASH_PATH":"C:\\Program Files\\Git\\bin\\bash.exe"}}
```

The full path is `C:\Program Files\Git\bin\bash.exe` (the default Git for Windows
install location). Adjust if you installed Git to a non-default path.

## Gate Behaviour Summary

| Dep | Type | Missing action |
|-----|------|----------------|
| bash | HARD | Blocks Agent spawns (exit 2) |
| git | HARD | Blocks Agent spawns (exit 2) |
| python / python3 / py | HARD | Blocks Agent spawns (exit 2) |
| realpath | HARD | Blocks Agent spawns (exit 2) |
| mktemp | HARD | Blocks Agent spawns (exit 2) |
| flock | OPTIONAL/advisory | Warned, never blocks |

`flock` is an optional advisory dependency used for concurrency locking. It is
not available on Windows or macOS by default but the harness degrades gracefully
without it — pipelines still run; the warning is informational only.

## Override

To bypass the gate entirely (e.g. during setup before deps are installed):

```powershell
$env:CLAUDE_DISABLE_DEPENDENCY_GATE = "1"
```

Or in `settings.json`:

```json
{"env":{"CLAUDE_DISABLE_DEPENDENCY_GATE":"1"}}
```

## Troubleshooting

- **"BLOCKED: harness prerequisites missing"**: one or more HARD deps are absent.
  Install the missing dep (shown in the message), then restart Claude Code.
- **"OPTIONAL not found: flock"**: advisory only — pipelines work, concurrency
  locking is degraded. No action required.
- Gate source: `hooks/harness-dependency-gate.sh`; probe: `hooks/_lib/harness-dependency-check.sh`
