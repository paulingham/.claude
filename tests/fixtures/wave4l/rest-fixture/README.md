# wave4-L REST-shape fixture

REST API shape (raw GitHub `/repos/.../pulls/N` and `.../files` responses).
Used by `wave4l_e2e_rest_to_consumer.bats` (H2) to exercise the real
server-write path: REST bytes in → server reshape → cache files written →
consumer reads → byte-identical to gh-CLI shape.

Files:
- `view-rest.json` — raw `/repos/o/r/pulls/N` REST response (uses
  `merged_at`, `merge_commit_sha`, label objects with `id/color/description`).
- `files-rest.json` — raw `/repos/o/r/pulls/N/files` JSON array.
- `diff.patch` — diff body (already same byte shape; gh and REST agree).

The peer fixture `tests/fixtures/wave4l/pr-fixture/` holds the gh-CLI shape
(post-reshape) used by the parity test in `wave4l_worker_cache_parity.bats`.
The REST fixture exists to verify the server's REST→gh reshape (C1, C2);
the gh-CLI fixture exists to verify cache-vs-gh consumer parity.

Regeneration: only when GitHub's REST schema changes. Capture via:
```
gh api repos/<o>/<r>/pulls/<N>           > view-rest.json
gh api repos/<o>/<r>/pulls/<N>/files     > files-rest.json
```
