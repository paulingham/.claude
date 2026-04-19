"""Glue between recall.search and rerank.rerank.

Acquires the embedder via the facade, applies rerank per source, emits
the AC11 stderr banner if anything went unavailable."""
import os
import sys

BANNER = ("[recall: lexical-only — run 'embedder doctor' "
          "to enable semantic rerank]\n")


def try_embedder():
    if os.environ.get("CLAUDE_EMBEDDER") != "fake":
        return None
    return _lazy_fake()


def _lazy_fake():
    from embedder._lib.fake import FakeEmbedder
    return FakeEmbedder()


def maybe_rerank(db_path, hits, query, limit, embedder):
    if embedder is None or not hits:
        return hits, embedder is None
    from recall._lib import rerank
    reranked, unavail = rerank.rerank(db_path, hits, query, limit, embedder)
    return reranked, unavail


def emit_banner_if_unavailable(unavailable):
    if unavailable:
        sys.stderr.write(BANNER)


def apply(hits, query, limit, db_path):
    emb = try_embedder()
    final, unavail = maybe_rerank(db_path, hits, query, limit, emb)
    emit_banner_if_unavailable(unavail)
    return final
