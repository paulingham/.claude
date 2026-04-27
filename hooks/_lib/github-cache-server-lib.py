"""Pure helpers for the github-cache MCP server (no I/O)."""
import os
import re

_PR_RE = re.compile(r"\bgh\s+pr\s+\w+\s+(\d+)\b")
_HTTPS_RE = re.compile(r"^https://github\.com/([^/]+)/([^/]+?)(?:\.git)?/?$")
_SSH_RE = re.compile(r"^git@github\.com:([^/]+)/([^/]+?)(?:\.git)?$")


def extract_pr_from_command(command):
    match = _PR_RE.search(command or "")
    return int(match.group(1)) if match else None


def extract_owner_repo(remote_url):
    return _match_https(remote_url) or _match_ssh(remote_url)


def _match_https(url):
    match = _HTTPS_RE.match(url or "")
    return (match.group(1), match.group(2)) if match else None


def _match_ssh(url):
    match = _SSH_RE.match(url or "")
    return (match.group(1), match.group(2)) if match else None


def cache_dir_for(session_id, pr):
    root = os.environ.get("CLAUDE_GH_CACHE_DIR", "/tmp/gh-pr-cache")
    return f"{root}/{session_id}-{pr}"
