"""Thin CLI wrapper: python3 arch_fitness_cli.py <lib_dir> -> JSON to stdout.

The shell hook parses this stable JSON contract. Nonzero exit only on crash.
"""
from __future__ import annotations

import json
import sys

from arch_fitness import detect_cycles


def main() -> None:
    if len(sys.argv) < 2:
        print("[]")
        return
    print(json.dumps(detect_cycles(sys.argv[1])))


if __name__ == "__main__":
    main()
