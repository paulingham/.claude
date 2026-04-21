"""Dispatch `python3 -m embedder <subcmd> [args]` to top-level modules.

Thin router only — subcommand logic lives in embedder.cli / embedder.backfill.
"""
import sys

from embedder import backfill, cli

SUBCOMMANDS = {"cli": cli.main, "backfill": backfill.main}


def main(argv):
    name = argv[0] if argv else "cli"
    target = SUBCOMMANDS.get(name, cli.main)
    return target(argv[1:] if name in SUBCOMMANDS else argv)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
