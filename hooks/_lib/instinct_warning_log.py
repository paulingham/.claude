"""JSONL warning emission for instinct loader (extracted Wave 5/B6.3)."""
import json
import subprocess
from pathlib import Path


def log_warning(path, reason):
    script = str(Path(__file__).parent / "log-injection.sh")
    resolved = json.dumps({"file": str(path), "reason": reason})
    cmd = ["bash", script, '{"tool_input":{"subagent_type":""}}',
           resolved, "load-warning", "instinct-injections.jsonl"]
    subprocess.run(cmd, stderr=subprocess.DEVNULL, check=False)
