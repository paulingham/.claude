"""Build a scratchpad_findings row tuple from a raw envelope dict."""
import hashlib

COLS = ("content_hash", "task_id", "category", "agent_role", "phase",
        "timestamp", "body", "is_private")

INSERT_SQL = (
    "INSERT OR IGNORE INTO scratchpad_findings (" + ",".join(COLS) +
    ") VALUES (" + ",".join(["?"] * len(COLS)) + ")")


def row_from_obj(obj):
    """Return a tuple matching COLS for scratchpad INSERT."""
    return (_hash(obj), obj.get("task_id") or "",
            obj.get("category") or "", obj.get("agent_role") or "",
            obj.get("phase") or "", obj.get("timestamp") or "",
            obj.get("body") or "", obj.get("is_private") or 0)


def _hash(obj):
    key = "|".join([obj.get(k) or "" for k in (
        "task_id", "category", "agent_role", "phase", "timestamp")])
    return hashlib.sha256(key.encode("utf-8")).hexdigest()
