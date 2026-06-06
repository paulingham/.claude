"""SWE-Pruner advisory context-pruning scorer.

Pure-Python deterministic scorer: no model call, no randomness.
Scores lines of orchestrator-assembled spawn prompt for relevance
to the agent's current goal and proposes drops (advisory only).

INVARIANT 1: Never mutates spawn context. Caller must exit 0 always.
INVARIANT 2: Syntax scaffolding is never proposed for drop.
"""
from __future__ import annotations

import hashlib
import os
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from swe_pruner_record import accumulate_block_stats

BLOCK_TYPE_MAP = {
    "scratchpad": "scratchpad",
    "protocol": "protocol",
    "protocols": "protocol",
    "session memory": "session_memory",
    "session_memory": "session_memory",
    "role": "role_doc",
    "role doc": "role_doc",
    "instincts": "instincts",
    "instinct": "instincts",
}

DEFAULT_THRESHOLD = 0.15

_SCAFFOLD_SOURCE_PATTERNS = (
    r"^import\s+",
    r"^from\s+\S+\s+import\s+",
    r"^class\s+",
    r"^def\s+",
    r"^func\s+",
    r"^export\s+",
    r"^#!",
)


@dataclass
class ContentBlock:
    """A named section of the spawn prompt."""
    block_type: str
    header: str
    lines: list[str] = field(default_factory=list)


def extract_goal_keywords(subagent_type: str, prompt) -> frozenset[str]:
    """Extract lowercase tokens >= 3 chars from subagent_type + prompt.

    Never raises. Returns frozenset of lowercase strings.
    """
    try:
        text = f"{subagent_type or ''} {prompt or ''}"
        tokens = re.findall(r"[a-z]{3,}", text.lower())
        return frozenset(tokens)
    except Exception:
        return frozenset()


def segment_content_blocks(prompt) -> list[ContentBlock]:
    """Split prompt on '## ' headers into typed ContentBlocks.

    Never raises. Returns empty list on empty/None prompt.
    """
    try:
        if not prompt:
            return []
        blocks: list[ContentBlock] = []
        current_block: Optional[ContentBlock] = None
        for raw_line in str(prompt).splitlines():
            if raw_line.startswith("## "):
                if current_block is not None:
                    blocks.append(current_block)
                header = raw_line[3:].strip()
                block_type = _classify_block_type(header)
                current_block = ContentBlock(block_type=block_type, header=header)
            elif current_block is not None:
                current_block.lines.append(raw_line)
        if current_block is not None:
            blocks.append(current_block)
        return blocks
    except Exception:
        return []


def _classify_block_type(header: str) -> str:
    key = header.lower().strip()
    for pattern, block_type in BLOCK_TYPE_MAP.items():
        if key == pattern or key.startswith(pattern):
            return block_type
    return "unknown"


def is_syntax_scaffold(line: str) -> bool:
    """Return True if line must never be proposed for drop.

    Primary guards: markdown fenced-code (```) and YAML frontmatter (---).
    Secondary: source-code identifiers embedded inside prompt code blocks.
    """
    stripped = line.strip()
    if not stripped:
        return False
    if stripped.startswith("```") or stripped == "---":
        return True
    return any(re.match(p, stripped) for p in _SCAFFOLD_SOURCE_PATTERNS)


def score_line(line: str, keywords: frozenset[str]) -> float:
    """Score a line for relevance in [0.0, 1.0]. Deterministic. No model."""
    if not line or not keywords:
        return 0.0
    tokens = set(re.findall(r"[a-z]{3,}", line.lower()))
    if not tokens:
        return 0.0
    return min(len(tokens & keywords) / len(tokens), 1.0)


def _get_threshold() -> float:
    raw = os.environ.get("CLAUDE_PRUNER_THRESHOLD", "")
    if not raw:
        return DEFAULT_THRESHOLD
    try:
        value = float(raw)
        return value if 0.0 <= value <= 1.0 else DEFAULT_THRESHOLD
    except (ValueError, TypeError):
        return DEFAULT_THRESHOLD


def propose_drops(
    block: ContentBlock,
    keywords: frozenset[str],
    threshold: Optional[float] = None,
) -> list[tuple[int, int]]:
    """Propose contiguous (start, end) ranges of lines to drop from block.

    INVARIANT 2: Syntax scaffold lines are NEVER included in drop ranges.
    """
    if threshold is None:
        threshold = _get_threshold()
    lines = block.lines
    drops: list[tuple[int, int]] = []
    run_start: Optional[int] = None
    for i, line in enumerate(lines):
        if is_syntax_scaffold(line):
            if run_start is not None:
                drops.append((run_start, i))
                run_start = None
            continue
        if score_line(line, keywords) < threshold:
            if run_start is None:
                run_start = i
        else:
            if run_start is not None:
                drops.append((run_start, i))
                run_start = None
    if run_start is not None:
        drops.append((run_start, len(lines)))
    return drops


def get_jsonl_path() -> Path:
    """Compute JSONL path via three-tier cascade; sanitise session against traversal."""
    base = (
        os.environ.get("CLAUDE_PLUGIN_DATA")
        or os.environ.get("CLAUDE_CONFIG_DIR")
        or os.path.join(os.environ.get("HOME", ""), ".claude")
    )
    session_raw = os.environ.get("CLAUDE_SESSION_ID") or f"local-{os.getpid()}"
    session = re.sub(r"[^A-Za-z0-9_-]", "_", session_raw)
    if not session or re.match(r"^_+$", session):
        session = f"local-{os.getpid()}"
    return Path(base) / "metrics" / session / "swe-pruner.jsonl"


def _extract_tool_input(payload) -> tuple[str, str]:
    """Return (subagent_type, prompt) from payload; never raises."""
    try:
        tool_input = (payload or {}).get("tool_input") or {}
    except Exception:
        tool_input = {}
    try:
        subagent_type = str(tool_input.get("subagent_type") or "unknown")[:64]
    except Exception:
        subagent_type = "unknown"
    try:
        prompt = str(tool_input.get("prompt") or "")
    except Exception:
        prompt = ""
    return subagent_type, prompt


def _sanitise_session() -> str:
    session_raw = os.environ.get("CLAUDE_SESSION_ID") or f"local-{os.getpid()}"
    session = re.sub(r"[^A-Za-z0-9_-]", "_", session_raw)
    return session if (session and not re.match(r"^_+$", session)) else f"local-{os.getpid()}"


def build_record(payload, proposals) -> dict:
    """Build the JSONL record dict. Never raises on malformed payload."""
    subagent_type, prompt = _extract_tool_input(payload)
    session = _sanitise_session()
    try:
        keywords = extract_goal_keywords(subagent_type, prompt)
        goal_hash = hashlib.sha256(
            " ".join(sorted(keywords)).encode()
        ).hexdigest()[:16]
    except Exception:
        keywords = frozenset()
        goal_hash = "0" * 16
    blocks_analyzed, total_lines, total_drops, total_tokens = accumulate_block_stats(proposals)
    prompt_chars = len(prompt)
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "session": session,
        "agent_role": subagent_type,
        "goal_hash": goal_hash,
        "keyword_count": len(keywords),
        "blocks_analyzed": blocks_analyzed,
        "total_lines_analyzed": total_lines,
        "total_proposed_drop_lines": total_drops,
        "total_estimated_tokens_saved": total_tokens,
        "prompt_total_chars": prompt_chars,
        "prompt_estimated_tokens": prompt_chars // 4,
    }
