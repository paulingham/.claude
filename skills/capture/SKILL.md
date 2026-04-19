---
name: "capture"
description: "Capture-time privacy: <private> tag stripping + allowlist classification applied before INSERT into observations / scratchpad_findings. Python stdlib only."
---

# Capture — Privacy

## What It Does

Two mechanisms run at capture time (before a row is hashed or inserted):

1. **`<private>...</private>` sanitizer** — removes tag AND contents from any
   text field (`file`, `outcome`, `command`, `searchable_text`, `body`). The
   user wraps sensitive content inline; the block never reaches disk.
2. **Allowlist classifier** — sets `is_private = 1` on rows whose sanitized
   `file` path matches a glob, OR whose sanitized content matches a regex.
   The row is still stored; the recall-time gate (S3/S4/S5) hides it from
   default queries.

Both run inside `capture._lib.privacy.apply(obj) -> obj'` and are wired into
the two production write surfaces:
- `reindex-memory/_lib/live_writer.py::_insert` (PostToolUse hook, live path)
- `reindex-memory/_lib/ingest.py::_insert_row` (reindex-from-JSONL, replay)

Sanitization happens BEFORE `content_hash` is computed, so live and replay
paths produce identical hashes for the same envelope (dedup integrity).

## Honesty Banner

1. **No retroactive redaction.** Rows inserted before S6 that contain
   `<private>` markers are untouched. Only new captures are sanitized.
2. **Hash domain changes at S6.** The same raw envelope produces a different
   `content_hash` post-S6 because `file` is sanitized before hashing. Dedup
   starts a fresh domain; previously-deduped pre-S6 rows do not collide
   with post-S6 re-captures of the same event.
3. **Allowlist classification is silent in v1.** A row flagged `is_private=1`
   by the allowlist emits no user-visible WARN; audit by querying the
   `is_private` column. A user-facing notification is deferred to S6.2.
4. **Scratchpad body sanitization runs at ingest.** Pre-S6 rows in
   `scratchpad_findings` may contain unsanitized content; re-reading them
   does not retroactively strip tags.

## `<private>` Tag

Wrap any inline content you want scrubbed:

```
The endpoint returned <private>Bearer eyJhbGciOi...</private> so auth works.
```

Persisted `searchable_text`:

```
The endpoint returned  so auth works.
```

Notes:
- Nested tags are handled (innermost stripped first via tempered-dot regex).
- Malformed (unclosed) tags return the original text unchanged.
- Depth cap is 10; exceeding returns original + stderr WARN, never raises.
- Fast path: if the literal substring `<private>` is absent, no regex work
  happens (sub-µs per call on representative payloads).

## Allowlist

### Default (shipped)

`skills/capture/privacy-allowlist.default.json` ships with the repo. File
globs (`.env*`, `*secret*`, `*.pem`, SSH keys, AWS/kube configs, etc.) and
content regexes (AWS/GitHub/Slack/Stripe/OpenAI/Google keys, JWT pattern).
No generic `[A-Za-z0-9]{32,}` catch-all — too many false positives on UUIDs
and git SHAs.

### User override

Drop your own at `~/.claude/privacy-allowlist.json`. If present, it
REPLACES the default (not merges). Copy-and-edit from the default:

```bash
cp ~/.claude/skills/capture/privacy-allowlist.default.json \
   ~/.claude/privacy-allowlist.json
$EDITOR ~/.claude/privacy-allowlist.json
```

### Format

```json
{
  "version": 1,
  "description": "...",
  "file_globs": ["*.env", ".ssh/*"],
  "content_regexes": ["AKIA[0-9A-Z]{16}\\b", "eyJ[A-Za-z0-9_\\-]+\\..*"]
}
```

- `file_globs` use `fnmatch` syntax. Case-sensitive on Linux + macOS
  (APFS is case-preserving but the capture layer uses plain string match).
- `content_regexes` are Python `re` patterns. Pre-compiled at load, cached
  by file mtime. Use `\\b` for word boundary to avoid superstring matches
  (e.g. `AKIA...extra` should not match `AKIA[0-9A-Z]{16}\\b`).

### Cold path

If neither the user file nor the default exists, capture behaves exactly
as S5 — no classification, no regex work, `is_private` defaults to 0
from the sanitizer path alone.

## Testing Your Allowlist

```python
import sys
sys.path.insert(0, "/Users/YOU/.claude/skills")
from capture._lib import privacy
out = privacy.apply({"file": ".env.prod", "outcome": "KEY=AKIA..."})
print(out["is_private"])  # 1
```

Or run the full recall gate via `reindex.py` then query:
`SELECT file, is_private FROM observations WHERE is_private = 1;`

## Rationale: JSON not YAML

The capture hot path is subject to a stdlib-only invariant (no PyPI deps
on PostToolUse). YAML would require `PyYAML`. JSON is in `json` stdlib,
parses in microseconds, and is schema-checkable. The trade-off (no inline
comments) is accepted; this doc and the `description` key substitute.
