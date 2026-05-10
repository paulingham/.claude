"""Argv-only CLI entry point for `python3 -m codebase_map.cli`.

Pinned by `pipeline-state/auto-codebase-map/plan.md` § Slice C AC18:
the harness hooks invoke this module via
`subprocess.run(["python3", "-m", "codebase_map.cli", "build", ROOT, CACHE], timeout=8)`.

The argv form is the contract — NO `python3 -c` shell-into-Python is
permitted from any hook. Reason: a SIGSEGV inside the tree-sitter
native lib must not poison the parent hook's exit code. With
subprocess isolation, abnormal child exits surface as a non-zero
return code; the hook treats that as a no-op (cache holds prior
result).

AC21 broadened catch surface: the CLI tolerates the full failure
surface of `tree_sitter_languages` — `(ImportError, OSError,
SystemError)` — and exits 0 with a one-line stderr warning. The hook
already treats non-zero subprocess exits as graceful no-ops, but we
make the CLI itself well-behaved so OSError-on-import doesn't trip
unrelated callers.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

DEGRADATION_PREFIX = "codebase-map: native lib unavailable —"


def main(argv: list[str] | None = None) -> int:
    """Dispatch the argv to the named subcommand.

    Returns 0 on success OR graceful degradation. Returns non-zero
    only on argv errors (caller mistake, not a runtime failure).
    """
    parser = _build_parser()
    args = parser.parse_args(argv)
    if args.subcommand == "build":
        return _build_command(args)
    parser.print_help(sys.stderr)
    return 2


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="codebase_map.cli")
    sub = parser.add_subparsers(dest="subcommand", required=True)
    build = sub.add_parser("build", help="Build the codebase-map digest")
    build.add_argument("repo_root", type=Path)
    build.add_argument("cache_dir", type=Path)
    build.add_argument("--max-files", type=int, default=500)
    build.add_argument("--budget", type=int, default=1024)
    return parser


def _build_command(args) -> int:
    """Run the build pipeline. Treat dependency failures as graceful no-op."""
    started = time.monotonic()
    try:
        return _run_build(args, started)
    except (ImportError, OSError, SystemError) as exc:
        # AC21 broadened catch — covers missing tree_sitter_languages,
        # dlopen arch mismatch, and fatal native abort surfaced as
        # SystemError. Exit 0 so the hook treats this as a graceful
        # degradation (no-op rebuild; cache holds prior result).
        print(
            f"{DEGRADATION_PREFIX} {exc.__class__.__name__}: {exc}",
            file=sys.stderr,
        )
        return 0


def _run_build(args, started: float) -> int:
    from codebase_map.build import build  # noqa: WPS433 — deferred import
    args.cache_dir.mkdir(parents=True, exist_ok=True)
    markdown = build(
        repo_root=args.repo_root,
        cache_dir=args.cache_dir,
        budget=args.budget,
        max_files=args.max_files,
    )
    out_path = args.cache_dir / "codebase-map.md"
    out_path.write_text(markdown)
    elapsed_ms = int((time.monotonic() - started) * 1000)
    summary = {
        "out": str(out_path),
        "bytes": len(markdown),
        "time_ms": elapsed_ms,
    }
    print(json.dumps(summary))
    return 0


if __name__ == "__main__":
    sys.exit(main())
