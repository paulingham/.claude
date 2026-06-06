"""Record-building helpers for swe_pruner.py.

Extracted to keep swe_pruner.py under the 300-line shape cap.
Single responsibility: accumulate per-block drop statistics into
the list of block dicts and aggregate totals used by build_record.
"""
from __future__ import annotations


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
