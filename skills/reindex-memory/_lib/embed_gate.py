"""Capture-time embed gate (S10): gated on model-file presence."""
import sys
from pathlib import Path

from _lib.embed_presence import models_present, warn_missing_once

_LOG = Path.home() / ".claude" / "db" / "live-writer.log"


def maybe_embed(con, obj, content_hash):
    if not models_present():
        warn_missing_once()
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
