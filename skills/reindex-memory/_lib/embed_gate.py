"""Opt-out gate for capture-time embeddings (AC9).

Default path (env unset) attempts embedding with graceful fallback.
Opt-out via CLAUDE_EMBED_AT_CAPTURE=0 returns immediately without
importing the embedder module — verified by test_opt_out_skips_embedder_import.
"""
import os
import sys
from pathlib import Path

_LOG = Path.home() / ".claude" / "db" / "live-writer.log"


def maybe_embed(con, obj, content_hash):
    if os.environ.get("CLAUDE_EMBED_AT_CAPTURE", "1") == "0":
        return
    _try_embed(con, obj, content_hash)


def _try_embed(con, obj, content_hash):
    try:
        _do_embed(con, obj, content_hash)
        _status().record_success()
    except Exception as exc:
        _log(f"embed failed for {content_hash[:16]}: {exc}")
        _status().record_failure(str(exc))


def _do_embed(con, obj, content_hash):
    from embedder.embedder import get_embedder  # lazy
    vec = get_embedder().encode(obj.get("searchable_text") or "")
    con.execute(
        "INSERT OR REPLACE INTO embeddings "
        "(content_hash, model_id, dim, vector) VALUES (?, ?, ?, ?)",
        (content_hash, "bge-small-en-v1.5", 384, vec))


def _status():
    from _lib import embed_status  # lazy
    return embed_status


def _log(msg):
    try:
        _LOG.parent.mkdir(parents=True, exist_ok=True)
        with open(_LOG, "a") as fh:
            fh.write(msg + "\n")
    except OSError:
        sys.stderr.write(msg + "\n")
