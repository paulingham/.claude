"""Prefetch tool: extract PR, resolve owner/repo, fetch + write cache."""
import os
import subprocess


def prefetch(args, lib, fetch):
    pr = lib.extract_pr_from_command(args.get("command", ""))
    if pr is None:
        return {"ok": False, "reason": "no PR number in command"}
    owner_repo = _resolve_owner_repo(lib)
    if not owner_repo:
        return {"ok": False, "reason": "unsupported remote"}
    return _fetch_and_write(owner_repo, pr, lib, fetch)


def _fetch_and_write(owner_repo, pr, lib, fetch):
    data = fetch.fetch_pr_data(owner_repo[0], owner_repo[1], pr)
    if not data.get("ok"):
        return data
    cache_dir = lib.cache_dir_for(os.environ.get("CLAUDE_SESSION_ID", "x"), pr)
    fetch.write_cache(cache_dir, data["view"], data["diff"], data["files"])
    return {"ok": True, "cache_dir": cache_dir}


def _resolve_owner_repo(lib):
    override = os.environ.get("_TEST_GH_OWNER_REPO")
    if override:
        return tuple(override.split("/", 1))
    return lib.extract_owner_repo(_git_remote())


def _git_remote():
    try:
        out = subprocess.check_output(
            ["git", "remote", "get-url", "origin"], stderr=subprocess.DEVNULL)
        return out.decode("utf-8").strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return ""
