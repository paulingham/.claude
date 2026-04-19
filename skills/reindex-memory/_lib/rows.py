"""Build an observations row tuple from a raw JSONL dict."""
from _lib import hash as hashmod


COLS = (
    "content_hash", "session_id", "project_hash", "timestamp", "tool",
    "file", "phase", "agent_role", "outcome", "tool_use_id", "arg_hash",
    "is_private", "searchable_text")

INSERT_SQL = (
    "INSERT OR IGNORE INTO observations (" + ",".join(COLS) +
    ") VALUES (" + ",".join(["?"] * len(COLS)) + ")")


def row_from_obj(obj, path):
    """Return a tuple matching COLS for INSERT INTO observations."""
    sid, ts, tool, f = _core_fields(obj)
    proj = obj.get("project_hash") or path.parent.name
    return (hashmod.content_hash(sid, ts, tool, f),
            sid, proj, ts, tool, f, *_aux_fields(obj),
            hashmod.searchable_text(tool, f, obj.get("outcome") or ""))


def _core_fields(obj):
    return (obj.get("session_id") or "", obj.get("timestamp") or "",
            obj.get("tool") or "", obj.get("file") or "")


def _aux_fields(obj):
    return (obj.get("phase") or "", obj.get("agent_role") or "",
            obj.get("outcome") or "", obj.get("tool_use_id") or "",
            obj.get("arg_hash") or "", 0)
