"""Shared JSONL appender for metrics emitters.

Single function: append one JSON record as a newline-terminated line to
{metrics_dir}/{filename}, creating the directory if needed.
"""
import json
import os


def append_jsonl(metrics_dir, filename, record):
    os.makedirs(metrics_dir, exist_ok=True)
    out = os.path.join(metrics_dir, filename)
    with open(out, "a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")
