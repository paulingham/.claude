# scripts/

Utility scripts for bootstrapping the claude harness on a fresh machine.

## `install-tools.sh`

OS-aware installer for the system tools and Python dependencies the harness
needs. Works on macOS (via `brew`), Ubuntu/Debian (`apt-get`), Fedora (`dnf`),
Arch (`pacman`), and Alpine (`apk`). Fails closed on any other OS.

### Usage

```bash
bash scripts/install-tools.sh --dry-run   # print commands, no side effects
bash scripts/install-tools.sh --yes       # actually install
bash scripts/install-tools.sh             # print commands + exit 1 (review first)
```

### What gets installed

System tools: `gh`, `jq`, `ripgrep`, `sqlite3`, `python3`, `bats`
(from `bats-core` on macOS), `shellcheck`.

Python venv (at `$CLAUDE_VENV_PATH`, default `$HOME/.claude/.venv`):
`onnxruntime`, `numpy`, `tokenizers` (embedder deps).

### Idempotence

Every tool is skipped if `command -v <tool>` already resolves. The venv is
created only on the first run; subsequent runs reuse it and re-invoke pip.

### Hermetic environment hooks

Tests and CI override any of the following to keep runs hermetic:

| Env var | Default | Effect when overridden |
|---|---|---|
| `CLAUDE_VENV_PATH` | `$HOME/.claude/.venv` | venv is created at this path |
| `PIP_CMD` | `pip install` | pip invocation (set to `echo PIP:` in tests) |
| `OS_RELEASE_PATH` | `/etc/os-release` | `detect_os` reads this file (fixture-driven tests) |
| `INSTALL_PKG_CMD_PRINTER` | _unset_ | if set, `install_pkg` prints the command via this tool instead of executing it |
| `CLAUDE_VENV_DRY_RUN` | _unset_ | if set, `ensure_venv` prints "would create…" and does not invoke `python3 -m venv` |

`--dry-run` automatically sets `INSTALL_PKG_CMD_PRINTER=echo`, `PIP_CMD=echo pip install`,
and `CLAUDE_VENV_DRY_RUN=1` so no side effects occur.

## Module layout

```
scripts/
├── install-tools.sh       # orchestrator (<=50 lines)
├── README.md              # this file
└── _lib/
    ├── detect-os.sh       # detect_os → macos|ubuntu|debian|fedora|arch|alpine|unknown
    ├── install-pkg.sh     # install_pkg <pkg> <os> — dispatches to the right PM
    └── ensure-venv.sh     # ensure_venv <pkg...> — idempotent venv + PIP_CMD
```

## Manual end-to-end verification (Docker)

The automated tests are fully hermetic — no real package manager is ever
invoked. To prove the installer works against a real apt-based system, run
the following manually. This is a **documented manual step**, not an
automated CI check.

```bash
docker run --rm -it ubuntu:24.04 bash -c '
  apt-get update -qq &&
  apt-get install -y -qq git sudo ca-certificates curl &&
  git clone <this-repo> /root/.claude &&
  bash /root/.claude/scripts/install-tools.sh --yes &&
  command -v bats && command -v shellcheck && command -v jq
'
```

Expected: the container prints install lines for each tool, the venv is
created at `/root/.claude/.venv`, and the three final `command -v` checks
resolve to non-empty paths.

On the build/dev machine (macOS), the equivalent real install completed
successfully — after `bash scripts/install-tools.sh --yes`, both
`command -v bats` and `command -v shellcheck` return non-empty paths.
This satisfies **AC3.9** for Slice 3 of the cloud-portability-setup plan.

## Shape constraints

All scripts follow the global shape budget: functions ≤ 5 lines, files
≤ 50 lines, cyclomatic complexity ≤ 5, nesting ≤ 2. `shellcheck` and
`bash -n` pass cleanly on every file under `scripts/`.
