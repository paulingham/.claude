"""Generic JSONL line iteration."""
from __future__ import annotations

import json
from pathlib import Path


def iter_jsonl(path: Path):
    if not path.exists():
        return
    with path.open() as fh:
        for i, line in enumerate(fh, 1):
            line = line.strip()
            if not line:
                continue
            try:
                yield i, json.loads(line)
            except json.JSONDecodeError:
                continue
