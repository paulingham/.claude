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

## `web-session-bootstrap.sh`

Sandbox bootstrap for Claude Code on the web. Makes a sandbox session use the harness source tree at `/home/user/.claude` instead of the near-empty runtime config dir at `/root/.claude`.

### Usage

```bash
bash scripts/web-session-bootstrap.sh                       # default source path
CLAUDE_SRC=/srv/claude bash scripts/web-session-bootstrap.sh  # custom path
```

Place this in whatever pre-session env mechanism the sandbox provides (a SessionStart hook, container entrypoint, or shell init file). **The session must restart after this runs** — `CLAUDE_CONFIG_DIR` is read at session start; mid-session changes are ignored.

### What it does

1. Exports `CLAUDE_CONFIG_DIR=$CLAUDE_SRC` so Claude Code reads `settings.json` and the full hook chain from the source tree.
2. Exports `CLAUDE_INSTINCTS_DIR`, `CLAUDE_AGENTS_DIR`, `CLAUDE_PIPELINE_STATE_DIR` so seed instincts, agent frontmatter, and in-progress pipeline state read from the source tree.
3. Symlinks shipped directories (`hooks/`, `skills/`, `rules/`, `agents/`, `knowledge/`, `orchestrator/`, `scripts/`, `learning/`, `agent-memory/`, `session-memory/`, `pipeline-state/`, `memory/`, `automation/`, `eval/`, `CLAUDE.md`, `README.md`, `settings.json`) from the source tree into `$HOME/.claude/` as a belt-and-braces fallback. Pure-runtime dirs (`metrics/`, `db/`, `sessions/`, `state/`, etc.) are left alone.
4. Verifies the layout (skills/hooks/agents counts) and fails fast if anything is missing.

### Idempotency

Safe to re-run. Already-correct symlinks are left in place. Real (non-symlink) files in `$HOME/.claude` are NOT clobbered — the script warns and skips them. To force replacement, remove the offending entry first:

```bash
rm -rf "$HOME/.claude/skills"  # then re-run the bootstrap
```

### Verification (post-restart)

Inside Claude Code:

- `/status` should show config sources from `/home/user/.claude/...`
- `/intake "test request"` should resolve (was "Unknown skill" before)
- A `Write` or `Edit` that creates a 51-line Python file should trigger `code-shape-check.sh` and block

### Convention

The bootstrap depends on the portable-config-dir convention documented in `protocols/agent-protocol.md` § Portable Config Dir — every config-loading reference inside the harness routes through `${CLAUDE_CONFIG_DIR:-$HOME/.claude}`. The drift gate at `tests/test_portable_config_dir.py` enforces this in CI.

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

All scripts follow the global shape budget (`protocols/engineering-invariants.md` § Code Shape): cyclomatic complexity ≤ 5, nesting ≤ 2. `shellcheck` and
`bash -n` pass cleanly on every file under `scripts/`.
