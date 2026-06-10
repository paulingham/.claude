# Setup & External Tools

This covers the external tools the harness uses, the macOS-vs-Linux gating, and the
Claude Code Cloud / web-sandbox bootstrap. For the basic install, see the
[README § Getting started](../README.md#getting-started).

## External tool reference

| Tool | Purpose | Install | Required? |
|------|---------|---------|-----------|
| [Dippy](https://github.com/ldayton/Dippy) | AST-based bash command safety | `brew install dippy` (macOS only) | Yes on macOS (dontAsk mode) |
| [claude-devtools](https://github.com/matt1398/claude-devtools) | Session observability | `brew install --cask claude-devtools` (macOS only) | Recommended on macOS |
| [parry-guard](https://github.com/vaporif/parry) | ML prompt-injection detection (DeBERTa v3) | `cargo install --git ... --features candle` | Required (needs Rust + HF token) |
| [hcom](https://github.com/aannoo/hcom) | Inter-agent communication for team phases | `npm install -g hcom` | Recommended |
| [agnix](https://github.com/agent-sh/agnix) | Config linting (385 rules) | `npx agnix ~/.claude/` | Optional |
| [Trail of Bits](https://github.com/trailofbits/skills) | Security analysis (5 plugins) | `claude plugin marketplace add` + install | Required |

### macOS install block

```bash
# Required: AST-based bash command safety (runs in dontAsk mode)
brew tap ldayton/dippy && brew install dippy

# Recommended: Session observability (token attribution, compaction visualization)
brew install --cask claude-devtools

# Required: ML-based prompt injection detection (pure Rust, no native deps)
# Needs: Rust toolchain — curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
# Needs: a free HuggingFace token (READ scope) — huggingface.co/settings/tokens
# Needs: accepting model terms at huggingface.co/ProtectAI/deberta-v3-small-prompt-injection-v2
cargo install --git https://github.com/vaporif/parry --features candle --no-default-features
mkdir -p ~/.parry-guard ~/.config/parry-guard
echo "YOUR_HF_TOKEN" > ~/.parry-guard/.hf-token && chmod 600 ~/.parry-guard/.hf-token

# Recommended: Inter-agent communication for team phases
npm install -g hcom

# Optional: Configuration linting (385 validation rules)
npx agnix ~/.claude/

# Required: Professional security skills (Trail of Bits)
claude plugin marketplace add trailofbits/skills
for p in supply-chain-risk-auditor variant-analysis differential-review sharp-edges static-analysis; do
    claude plugin install "$p@trailofbits"
done
```

## Linux / Claude Code Cloud

The macOS block above is Homebrew-first. On Ubuntu/Debian/Fedora — including a fresh Claude
Code Cloud VM — use `scripts/install-tools.sh` instead. It detects the distro via
`/etc/os-release`, installs `gh`, `jq`, `ripgrep`, `sqlite3`, `python3>=3.11`, and the
C/OpenSSL build toolchain via the native package manager, and bootstraps the shared
virtualenv at `$HOME/.claude/.venv`. It's idempotent and accepts `--yes` for unattended runs.

```bash
bash "$HOME/.claude/scripts/install-tools.sh" --yes   # unattended install
bash "$HOME/.claude/setup.sh"                          # then run the bootstrap
```

`dippy` and `claude-devtools` are Homebrew-only and skipped on Linux by default.

### `CLAUDE_REQUIRE_DIPPY` — Homebrew-only tool gating

| Value | macOS | Linux | Use |
|-------|-------|-------|-----|
| unset | install | skip | Default — best-effort per-platform |
| `1` | install | install | Opt-in on Linux (you have a working install path) |
| `0` | skip | skip | Opt-out on macOS (e.g. minimal dev shell) |

Skipped installs emit a single `INFO:` line explaining why (platform + env-var status).

### Ubuntu clone-and-run

```bash
git clone git@github.com:<org>/claude-harness.git "$HOME/.claude"
bash "$HOME/.claude/scripts/install-tools.sh" --yes
bash "$HOME/.claude/tests/shell/run.sh" --require-bats  # verifies install
```

## Web sandbox bootstrap

Claude Code on the web mounts the harness at `/home/user/.claude` but runs the session as
`HOME=/root`, so `~/.claude` resolves to a near-empty runtime dir and the harness silently
degrades (1 hook / 1 skill registered instead of the full chain).
`scripts/web-session-bootstrap.sh` makes a sandbox session use the source tree:

```bash
bash /home/user/.claude/scripts/web-session-bootstrap.sh
```

Place this in whatever pre-session env mechanism the sandbox provides (a SessionStart hook,
container entrypoint, or shell init file). **The session must restart afterwards** —
`CLAUDE_CONFIG_DIR` is read at session start; mid-session changes don't take effect.

What it does:

1. Exports `CLAUDE_CONFIG_DIR=/home/user/.claude` (the official env var for relocating config).
2. Exports `CLAUDE_INSTINCTS_DIR`, `CLAUDE_AGENTS_DIR`, `CLAUDE_PIPELINE_STATE_DIR` so seed
   instincts, agent frontmatter, and in-progress pipeline state read from the source tree.
3. Symlinks shipped dirs (`hooks/`, `skills/`, `rules/`, `agents/`, …) into `$HOME/.claude/`
   as a fallback for any code path that still hardcodes `$HOME/.claude/...`. Pure-runtime dirs
   (`metrics/`, `db/`, `sessions/`, `state/`) stay where Claude Code's runtime puts them.
4. Verifies the layout (skills/hooks/agents counts) and fails fast if anything is missing.

Idempotent and safe to re-run; refuses to clobber non-symlink files (warns and skips). The
source-tree path is configurable via `CLAUDE_SRC=...`:

```bash
CLAUDE_SRC=/srv/claude-harness bash scripts/web-session-bootstrap.sh
```

After bootstrap + restart, verify: `/harness:intake "test"` should resolve (was "Unknown
skill" before), and an Edit on a 301-line `.py` file should fire `code-shape-check.sh`. The
portable-config-dir convention is documented in `protocols/agent-protocol.md` § Portable Config Dir.
