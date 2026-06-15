#!/usr/bin/env python3
"""Generate-and-check README count tokens from filesystem reality.

Usage:
    python3 scripts/sync_doc_counts.py --check [--repo-root PATH]
    python3 scripts/sync_doc_counts.py --write  [--repo-root PATH]

WHY: README.md carries four count tokens that must stay in sync with
filesystem globs.  Manual editing is error-prone; this generator is the SSOT.
--check is the CI staleness gate; --write repairs drift in one call.
"""
import os
import pathlib
import re
import sys


# WHY: os.scandir raises PermissionError on unreadable dirs (glob silently returns
# empty); this probe ensures Law-8b fail-closed behaviour for A7.
def _skill_dirs(repo_root: pathlib.Path) -> list:
    skills_root = repo_root / "skills"
    list(os.scandir(skills_root))
    return list(repo_root.glob("skills/*/SKILL.md"))


# WHY: SSOT for skill count; test_thinking_defaults delegates here so the
# glob rule is defined once and shared.
def _count_skills(repo_root: pathlib.Path) -> int:
    return sum(1 for p in _skill_dirs(repo_root) if p.parent.name != "_template")


# WHY: SSOT for agent count; test_thinking_defaults delegates here.
def _count_agents(repo_root: pathlib.Path) -> int:
    return len(list(repo_root.glob("agents/*.md")))


def compute_counts(repo_root: pathlib.Path) -> dict:
    return {
        "skills": _count_skills(repo_root),
        "agents": _count_agents(repo_root),
    }


# WHY: one re.sub per anchor so each is a no-op when that anchor is absent
# (missing-anchor tolerance required by AC A9 / C11 bats fake_repo).
def _sub_heading(text: str, n: int) -> str:
    return re.sub(r"(?m)^(## Skills \()\d+(\))", rf"\g<1>{n}\2", text)


def _sub_arch_skills(text: str, n: int) -> str:
    return re.sub(r"(skills/\s*#\s*)\d+(\s+skills\b)", rf"\g<1>{n}\2", text)


def _sub_prose_skills(text: str, n: int) -> str:
    return re.sub(r"\(\d+\s+skills,\s+grouped", f"({n} skills, grouped", text)


def _sub_arch_agents(text: str, n: int) -> str:
    return re.sub(r"(#\s*)\d+(\s+specialized agent)", rf"\g<1>{n}\2", text)


def render_readme(text: str, counts: dict) -> str:
    text = _sub_heading(text, counts["skills"])
    text = _sub_arch_skills(text, counts["skills"])
    text = _sub_prose_skills(text, counts["skills"])
    return _sub_arch_agents(text, counts["agents"])


def _readme_path(repo_root: pathlib.Path) -> pathlib.Path:
    return repo_root / "README.md"


# WHY: Law-8b fail-closed — missing README must refuse, not silently pass.
def _guard_readme(readme: pathlib.Path) -> int:
    if readme.exists():
        return 0
    print(f"ERROR: {readme} not found — cannot check counts", file=sys.stderr)
    return 1


# WHY: Law-8b fail-closed — unreadable skills dir must refuse, not silently pass.
def _guard_counts(repo_root: pathlib.Path) -> tuple:
    try:
        return compute_counts(repo_root), 0
    except PermissionError as exc:
        print(f"ERROR: cannot read skills dir: {exc}", file=sys.stderr)
        return None, 1


def _is_synced(readme: pathlib.Path, counts: dict) -> bool:
    return render_readme(readme.read_text(), counts) == readme.read_text()


def _drift_msg(counts: dict) -> str:
    return (
        f"ERROR: README.md count tokens out of sync "
        f"(skills={counts['skills']}, agents={counts['agents']}). "
        "Run: python3 scripts/sync_doc_counts.py --write"
    )


def _check_synced(readme: pathlib.Path, counts: dict) -> int:
    if _is_synced(readme, counts):
        return 0
    print(_drift_msg(counts), file=sys.stderr)
    return 1

def _check_guards(readme: pathlib.Path, repo_root: pathlib.Path) -> tuple:
    if _guard_readme(readme):
        return None, 1
    return _guard_counts(repo_root)

def check(repo_root: pathlib.Path) -> int:
    readme = _readme_path(repo_root)
    counts, err = _check_guards(readme, repo_root)
    if err:
        return 1
    return _check_synced(readme, counts)

def write(repo_root: pathlib.Path) -> None:
    readme = _readme_path(repo_root)
    if not readme.exists():
        raise FileNotFoundError(f"{readme} not found")
    counts = compute_counts(repo_root)
    readme.write_text(render_readme(readme.read_text(), counts))

def _apply_mode(argv: list, i: int, state: dict) -> int:
    state["mode"] = argv[i].lstrip("-")
    return i + 1

def _apply_repo_root(argv: list, i: int, state: dict) -> int:
    state["repo_root"] = pathlib.Path(argv[i + 1])
    return i + 2

def _apply_argv_token(argv: list, i: int, state: dict) -> int:
    if argv[i] in ("--write", "--check"):
        return _apply_mode(argv, i, state)
    if argv[i] == "--repo-root":
        return _apply_repo_root(argv, i, state)
    return i + 1

def _parse_argv(argv: list) -> tuple:
    state = {"mode": None, "repo_root": pathlib.Path(__file__).parent.parent}
    i = 0
    while i < len(argv):
        i = _apply_argv_token(argv, i, state)
    return state["mode"], state["repo_root"]

def _dispatch(mode: str, repo_root: pathlib.Path) -> int:
    if mode == "check":
        return check(repo_root)
    write(repo_root)
    return 0

def _usage() -> int:
    print("Usage: sync_doc_counts.py --check|--write [--repo-root PATH]",
          file=sys.stderr)
    return 1

def main(argv: list) -> int:
    mode, repo_root = _parse_argv(argv)
    if mode is None:
        return _usage()
    return _dispatch(mode, repo_root)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
