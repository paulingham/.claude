"""Entry point: `python3 skills/mcp_memory/server.py` runs stdio JSON-RPC."""
import sys
from pathlib import Path


def _bootstrap_paths():
    skills = Path(__file__).resolve().parents[1]
    if str(skills) not in sys.path:
        sys.path.insert(0, str(skills))


def main():
    _bootstrap_paths()
    from mcp_memory._lib import io_loop, tools
    io_loop.serve(sys.stdin, sys.stdout, tools.dispatch)


if __name__ == "__main__":
    main()
