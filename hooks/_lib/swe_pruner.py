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

BLOCK_TYPE_MAP = {
    # Canonical orchestrator-injected headers (prefix match, case-insensitive)
    "pipeline scratchpad": "scratchpad",
    "session context": "session_memory",
    "learned patterns": "instincts",
    "your project knowledge": "role_doc",
    # Short-form aliases for backward compatibility
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
    """Extract tokens from the goal region only — NOT from prunable context blocks.

    Goal region: subagent_type + pre-header preamble + non-prunable blocks
    (role_doc, unknown). Excludes scratchpad/session_memory/instincts/protocol
    so the scorer is not self-referential. Never raises.
    """
    _PRUNABLE = frozenset({"scratchpad", "session_memory", "instincts", "protocol"})
    try:
        prompt_str = str(prompt or "")
        preamble = _extract_preamble(prompt_str)
        goal_blocks = " ".join(
            " ".join(b.lines)
            for b in segment_content_blocks(prompt_str)
            if b.block_type not in _PRUNABLE
        )
        text = " ".join(filter(None, [str(subagent_type or ""), preamble, goal_blocks]))
        return frozenset(re.findall(r"[a-z]{3,}", text.lower()))
    except Exception:
        return frozenset()


def _extract_preamble(prompt_str: str) -> str:
    """Return prompt text before the first '## ' header."""
    lines: list[str] = []
    for line in prompt_str.splitlines():
        if line.startswith("## "):
            break
        lines.append(line)
    return " ".join(lines)


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


def _sanitise_session() -> str:
    session_raw = os.environ.get("CLAUDE_SESSION_ID") or f"local-{os.getpid()}"
    session = re.sub(r"[^A-Za-z0-9_-]", "_", session_raw)
    return session if (session and not re.match(r"^_+$", session)) else f"local-{os.getpid()}"


def get_jsonl_path() -> Path:
    """Compute JSONL path via three-tier cascade; sanitise session against traversal."""
    base = (
        os.environ.get("CLAUDE_PLUGIN_DATA")
        or os.environ.get("CLAUDE_CONFIG_DIR")
        or os.path.join(os.environ.get("HOME", ""), ".claude")
    )
    session = _sanitise_session()
    return Path(base) / "metrics" / session / "swe-pruner.jsonl"


def _extract_tool_input(payload) -> tuple[str, str, str]:
    """Return (subagent_type, prompt, task_id) from payload; never raises."""
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
    try:
        task_id = str(tool_input.get("task_id") or "")[:64]
    except Exception:
        task_id = ""
    return subagent_type, prompt, task_id


def accumulate_block_stats(proposals) -> tuple[list[dict], int, int, int]:
    """Compute per-block drop stats from (ContentBlock, ranges) pairs.

    Returns (blocks_analyzed, total_lines, total_drop_lines, total_tokens_saved).
    Never raises; returns empty-zero tuple on any error.
    """
    blocks_analyzed: list[dict] = []
    total_lines = 0
    total_drop_lines = 0
    total_tokens_saved = 0
    try:
        for block, ranges in (proposals or []):
            drop_chars = sum(
                len(block.lines[i])
                for start, end in ranges
                for i in range(start, end)
                if i < len(block.lines)
            )
            tokens_saved = drop_chars // 4
            drop_lines = sum(end - start for start, end in ranges)
            blocks_analyzed.append({
                "block_type": block.block_type,
                "total_lines": len(block.lines),
                "proposed_drop_lines": drop_lines,
                "proposed_drop_ranges": [[s, e] for s, e in ranges],
                "estimated_tokens_saved": tokens_saved,
            })
            total_lines += len(block.lines)
            total_drop_lines += drop_lines
            total_tokens_saved += tokens_saved
    except Exception:
        pass
    return blocks_analyzed, total_lines, total_drop_lines, total_tokens_saved


def build_record(payload, proposals) -> dict:
    """Build the JSONL record dict. Never raises on malformed payload."""
    subagent_type, prompt, task_id = _extract_tool_input(payload)
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
        "task_id": task_id,
        "goal_hash": goal_hash,
        "keyword_count": len(keywords),
        "blocks_analyzed": blocks_analyzed,
        "total_lines_analyzed": total_lines,
        "total_proposed_drop_lines": total_drops,
        "total_estimated_tokens_saved": total_tokens,
        "prompt_total_chars": prompt_chars,
        "prompt_estimated_tokens": prompt_chars // 4,
    }
