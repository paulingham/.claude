"""Glue between recall.search and rerank.rerank.

Acquires the embedder via the facade, applies rerank per source, emits
the AC11 stderr banner if anything went unavailable."""
import sys

BANNER = ("[recall: lexical-only — run 'embedder doctor' "
          "to enable semantic rerank]\n")


def try_embedder():
    try:
        from embedder.embedder import get_embedder
        return get_embedder()
    except Exception:
        return None


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
