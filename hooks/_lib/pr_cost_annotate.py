#!/usr/bin/env python3
"""Annotate a GitHub PR body with its pipeline cost.

Entry point for Ship Step 6: after CI goes green, compute the real
cost from the live session transcript and PATCH the PR body, replacing
the sentinel line written at PR-open time.

Public API:
    resolve_live_transcript(projects_root, cwd_slug) -> str | None
    format_cost_line(usage_by_model) -> str
    replace_sentinel(body, new_line) -> str
    main()  (CLI: python3 pr_cost_annotate.py <pr-number>
                   [--transcript PATH] [--repo owner/repo])

WHY fail-open: this script edits live PR bodies on every Ship;
a bug must never block a merge or wedge the Ship phase.
"""
import argparse
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

from cost_estimator import estimate_cost_usd
from transcript_usage import sum_usage_by_model

_SENTINEL_PREFIX = "**Pipeline cost:**"
_SENTINEL_RE = re.compile(r"^\*\*Pipeline cost:\*\*.*$", re.MULTILINE)


def _top_level_jsonl(slug_dir: Path) -> list:
    return [
        p for p in slug_dir.glob("*.jsonl")
        if p.is_file() and "subagents" not in p.parts
    ]


def _newest_path(candidates: list) -> str:
    return str(max(candidates, key=lambda p: p.stat().st_mtime))


def resolve_live_transcript(projects_root: str, cwd_slug: str):
    slug_dir = Path(projects_root) / cwd_slug
    if not slug_dir.is_dir():
        return None
    candidates = _top_level_jsonl(slug_dir)
    return _newest_path(candidates) if candidates else None


def _usage_to_records(usage_by_model: dict) -> list:
    return [{"model": m, **counts} for m, counts in usage_by_model.items()]


def _model_cost_part(model: str, counts: dict) -> str:
    cost = estimate_cost_usd([{"model": model, **counts}])
    return f"{model} ${cost:.2f}"


def _breakdown(usage_by_model: dict) -> str:
    return ", ".join(_model_cost_part(m, c) for m, c in usage_by_model.items())


def format_cost_line(usage_by_model: dict) -> str:
    total = estimate_cost_usd(_usage_to_records(usage_by_model))
    base = f"{_SENTINEL_PREFIX} ${total:.2f}"
    if not usage_by_model:
        return base
    return f"{base} ({_breakdown(usage_by_model)})"


def _has_sentinel(body: str) -> bool:
    return bool(_SENTINEL_RE.search(body))


def _append_line(body: str, new_line: str) -> str:
    sep = "\n" if body and not body.endswith("\n") else ""
    return body + sep + new_line


def replace_sentinel(body: str, new_line: str) -> str:
    if _has_sentinel(body):
        return _SENTINEL_RE.sub(new_line, body, count=1)
    return _append_line(body, new_line)


def _run_gh(*args: str) -> str:
    result = subprocess.run(list(args), capture_output=True, text=True, check=True)
    return result.stdout.strip()


def _fetch_pr_body(pr_number: str, repo: str) -> str:
    return _run_gh("gh", "api", f"repos/{repo}/pulls/{pr_number}", "-q", ".body")


def _resolve_repo() -> str:
    return _run_gh(
        "gh", "repo", "view", "--json", "nameWithOwner", "-q", ".nameWithOwner",
    )


def _write_tmp(content: str) -> str:
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".txt", delete=False, encoding="utf-8",
    ) as tmp:
        tmp.write(content)
        return tmp.name


def _gh_patch(pr_number: str, repo: str, tmp_path: str) -> None:
    subprocess.run(
        ["gh", "api", f"repos/{repo}/pulls/{pr_number}",
         "-X", "PATCH", "-F", f"body=@{tmp_path}"],
        check=True, capture_output=True,
    )


def _patch_pr_body(pr_number: str, repo: str, new_body: str) -> None:
    tmp_path = _write_tmp(new_body)
    try:
        _gh_patch(pr_number, repo, tmp_path)
    finally:
        os.unlink(tmp_path)


def _cwd_slug() -> str:
    return Path(os.getcwd()).as_posix().replace("/", "-").lstrip("-")


def _default_transcript() -> str | None:
    return resolve_live_transcript(
        os.path.expanduser("~/.claude/projects"), _cwd_slug()
    )


def _resolve_transcript(args) -> str | None:
    return args.transcript if args.transcript else _default_transcript()


def _add_args(p: argparse.ArgumentParser) -> None:
    p.add_argument("pr_number", help="Pull request number")
    p.add_argument("--transcript", default=None, help="Session transcript JSONL override")
    p.add_argument("--repo", default=None, help="owner/repo override")


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Annotate PR body with pipeline cost")
    _add_args(p)
    return p


def _compute_usage(args) -> dict:
    path = _resolve_transcript(args)
    return sum_usage_by_model(path) if path else {}


def _run() -> None:
    args = _build_parser().parse_args()
    repo = args.repo or _resolve_repo()
    body = _fetch_pr_body(args.pr_number, repo)
    new_body = replace_sentinel(body, format_cost_line(_compute_usage(args)))
    if new_body != body:
        _patch_pr_body(args.pr_number, repo, new_body)


def main() -> None:
    try:
        _run()
    except Exception as exc:  # noqa: BLE001 — fail-open: never block Ship
        print(f"pr_cost_annotate: non-fatal error — {exc}", file=sys.stderr)
        sys.exit(0)


if __name__ == "__main__":
    main()
