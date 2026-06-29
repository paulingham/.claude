"""Seed 10 developer-facing toggles into the user-level settings.json.

Target path resolution (mirrors bootstrap_settings.py:41):
  CLAUDE_SETTINGS_PATH override (test seam) else
  ${CLAUDE_CONFIG_DIR or $HOME/.claude}/settings.json.

SSOT: reads toggle defaults from harness_root()/settings.json at runtime.
Falls back to the hardcoded map when that file is missing or unreadable.
"""
from __future__ import annotations
import json
import logging
import os
import sys
import tempfile
from pathlib import Path

# WHY: harness_paths lives in the same directory; insert only if needed.
_LIB_DIR = str(Path(__file__).parent)
if _LIB_DIR not in sys.path:
    sys.path.insert(0, _LIB_DIR)
from harness_paths import harness_root  # noqa: E402

logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")
_LOG = logging.getLogger(__name__)

# The 10 allowlisted toggle keys (the ONLY keys this seed may write).
# Break-glass keys (CLAUDE_DISABLE_QUALITY_GATE, CLAUDE_DISABLE_TOOL_ALLOWLIST,
# CLAUDE_INTAKE_BACKSTOP, CLAUDE_DISABLE_FRESHNESS_GUARD,
# CLAUDE_DISABLE_RUNTIME_STATE_GUARD) are intentionally absent.
TOGGLE_ALLOWLIST = (
    "CLAUDE_PIPELINE_MODE",
    "CLAUDE_ENABLE_TRACE",
    "CLAUDE_DISABLE_SANDBOX_VERIFY",
    "CLAUDE_DISABLE_VLM_CRITIC",
    "CLAUDE_DISABLE_SWE_PRUNER",
    "CLAUDE_DISABLE_INSTINCT_INJECTION",
    "CLAUDE_DISABLE_WORKTREE_REAPER",
    "CLAUDE_VISIBLE_TEAMS",
    "CLAUDE_PLAN_CACHE_MODE",
    "ENABLE_TOOL_SEARCH",
)

# Hardcoded fallback defaults (mirrors repo settings.json env block).
# WHY: used when harness_root()/settings.json is missing or unreadable.
_FALLBACK_DEFAULTS: dict[str, str] = {
    "CLAUDE_PIPELINE_MODE": "autonomous",
    "CLAUDE_ENABLE_TRACE": "0",
    "CLAUDE_DISABLE_SANDBOX_VERIFY": "0",
    "CLAUDE_DISABLE_VLM_CRITIC": "0",
    "CLAUDE_DISABLE_SWE_PRUNER": "0",
    "CLAUDE_DISABLE_INSTINCT_INJECTION": "0",
    "CLAUDE_DISABLE_WORKTREE_REAPER": "0",
    "CLAUDE_VISIBLE_TEAMS": "0",
    "CLAUDE_PLAN_CACHE_MODE": "shadow",
    "ENABLE_TOOL_SEARCH": "true",
}

# Hardcoded fallback docs (verbatim _doc_ strings from repo settings.json env block).
# WHY: fallback-created files must be self-documenting even when SSOT is unreadable.
_FALLBACK_DOCS: dict[str, str] = {
    "CLAUDE_PIPELINE_MODE": (
        "Pipeline execution mode. Values: autonomous (no human gates) | interactive"
        " (pauses at decision points). Default: autonomous. Values are case-sensitive."
        " Edit here (user layer) — managed no longer pins this key."
    ),
    "CLAUDE_ENABLE_TRACE": (
        "Enable prompt-tracing for agent spawns. Values: 0 (off) | 1 (on). Default: 0."
        " Use 1 to debug agent prompt construction. 0/1 exact. Edit here (user layer)"
        " — managed no longer pins this key. Per-session alternative: /harness:debug-trace on"
        " (overrides both static layers for the current session)."
    ),
    "CLAUDE_DISABLE_SANDBOX_VERIFY": (
        "Disable Final-Gate sandbox-verify engineer. Values: 0 (runs) | 1 (skipped)."
        " Default: 0. 0/1 exact."
    ),
    "CLAUDE_DISABLE_VLM_CRITIC": (
        "Disable Final-Gate visual-diff critic. Values: 0 (runs) | 1 (skipped)."
        " Default: 0. 0/1 exact."
    ),
    "CLAUDE_DISABLE_SWE_PRUNER": (
        "Disable SWE-bench candidate pruner. Values: 0 (runs) | 1 (skipped)."
        " Default: 0. 0/1 exact."
    ),
    "CLAUDE_DISABLE_INSTINCT_INJECTION": (
        "Disable instinct injection into agent prompts. Values: 0 (injects) | 1 (skipped)."
        " Default: 0. 0/1 exact."
    ),
    "CLAUDE_DISABLE_WORKTREE_REAPER": (
        "Disable the worktree reaper (SessionStart cleanup of stale worktrees)."
        " Values: 0 (runs) | 1 (skipped). Default: 0. 0/1 exact."
    ),
    "CLAUDE_VISIBLE_TEAMS": (
        "Enable visible team dispatch (tmux panes) instead of parallel subagents."
        " Values: 0 (parallel subagents) | 1 (visible teams). Default: 0. 0/1 exact."
    ),
    "CLAUDE_PLAN_CACHE_MODE": (
        "Plan-cache mode. Values: off | shadow (record, no reuse) | on (reuse cached plan)."
        " Default: shadow. Values are case-sensitive (e.g. shadow not Shadow)."
    ),
    "ENABLE_TOOL_SEARCH": (
        "Pin explicit. Default already defers all MCP tools behind ToolSearch (lowest"
        " upfront-token cost). `auto` was REJECTED at intake because its 10%-context-window"
        " threshold mode loads small servers upfront — INCREASES tool-definition tokens vs"
        " default. This pin guards against a future Claude Code default flip. Source:"
        " https://code.claude.com/docs/en/mcp#scale-with-mcp-tool-search. Requires"
        " Sonnet 4+ or Opus 4+ (Haiku unsupported). See"
        " protocols/_proposals/2026-05-15-mcp-tool-config.md for full rationale."
    ),
}

def _target_path() -> Path:
    override = os.environ.get("CLAUDE_SETTINGS_PATH")
    if override:
        return Path(override)
    base = os.environ.get("CLAUDE_CONFIG_DIR") or str(Path.home() / ".claude")
    return Path(base) / "settings.json"

def _default_for(key: str, defaults: dict[str, str]) -> str:
    return defaults.get(key, _FALLBACK_DEFAULTS[key])

def _extract_toggle_defaults(env: dict) -> dict[str, str]:
    return {k: env[k] for k in TOGGLE_ALLOWLIST if k in env}

def _extract_toggle_docs(env: dict) -> dict[str, str]:
    return {k: env[f"_doc_{k}"] for k in TOGGLE_ALLOWLIST if f"_doc_{k}" in env}

def _ssot_complete(defaults: dict[str, str]) -> bool:
    return len(defaults) == len(TOGGLE_ALLOWLIST)

def _parse_ssot_env(env: dict) -> tuple[dict, dict] | None:
    defaults = _extract_toggle_defaults(env)
    docs = _extract_toggle_docs(env)
    return (defaults, docs) if _ssot_complete(defaults) else None

def _parse_ssot_file(path: Path) -> tuple[dict, dict] | None:
    try:
        env = json.loads(path.read_text()).get("env", {})
        return _parse_ssot_env(env)
    except Exception:  # noqa: BLE001
        return None

def _read_ssot_defaults() -> tuple[dict[str, str], dict[str, str]]:
    result = _parse_ssot_file(harness_root() / "settings.json")
    if result is not None:
        return result
    return _FALLBACK_DEFAULTS.copy(), _FALLBACK_DOCS.copy()

def _load_existing(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return None

def _build_seed_block(defaults: dict[str, str], docs: dict[str, str]) -> dict:
    block: dict = {}
    for key in TOGGLE_ALLOWLIST:
        block[key] = _default_for(key, defaults)
        if key in docs:
            block[f"_doc_{key}"] = docs[key]
    return block

def _insert_key(env: dict, key: str, defaults: dict[str, str]) -> bool:
    if key in env:
        return False
    env[key] = _default_for(key, defaults)
    return True

def _insert_doc(env: dict, key: str, docs: dict[str, str]) -> bool:
    doc_key = f"_doc_{key}"
    if doc_key in env or key not in docs:
        return False
    env[doc_key] = docs[key]
    return True

def _insert_pair(env: dict, key: str, defaults: dict, docs: dict) -> bool:
    added = _insert_key(env, key, defaults)
    added = _insert_doc(env, key, docs) or added
    return added

def _merge_into_env(env: dict, defaults: dict, docs: dict) -> bool:
    # WHY: list() forces full iteration — any() short-circuits and skips keys.
    results = [_insert_pair(env, k, defaults, docs) for k in TOGGLE_ALLOWLIST]
    return any(results)

def _write_json_to_fd(fd: int, data: dict) -> None:
    # WHY: deliberately NOT settings_patch — sort_keys would reorder dev keys (AC2).
    with os.fdopen(fd, "w") as fh:
        json.dump(data, fh, indent=2)
        fh.write("\n")

def _replace_via_tempfile(path: Path, data: dict) -> None:
    fd, tmp_name = tempfile.mkstemp(dir=path.parent, suffix=".json.tmp")
    try:
        _write_json_to_fd(fd, data)
        os.replace(tmp_name, path)
    except Exception:
        os.unlink(tmp_name)
        raise

def _write_atomic(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    _replace_via_tempfile(path, data)

def _seed_absent(target: Path, defaults: dict, docs: dict) -> None:
    _write_atomic(target, {"env": _build_seed_block(defaults, docs)})

def _shape_valid(data: dict) -> bool:
    return isinstance(data, dict) and isinstance(data.get("env", {}), dict)

def _merge_and_write(target: Path, data: dict, defaults: dict, docs: dict) -> None:
    if not _shape_valid(data):
        _LOG.warning("seed_user_settings: unexpected JSON shape in %s — skipping", target)
        return
    env = data.setdefault("env", {})
    if _merge_into_env(env, defaults, docs):
        _write_atomic(target, data)

def _seed_present(target: Path, defaults: dict, docs: dict) -> None:
    data = _load_existing(target)
    if data is None:
        _LOG.warning("seed_user_settings: cannot parse %s — skipping", target)
        return
    _merge_and_write(target, data, defaults, docs)

def seed_main() -> None:
    target = _target_path()
    defaults, docs = _read_ssot_defaults()
    if not target.exists():
        _seed_absent(target, defaults, docs)
    else:
        _seed_present(target, defaults, docs)

if __name__ == "__main__":
    seed_main()
