# S5.1 Fixtures

## ort_api_indices.json

Locks the `OrtApi` function-pointer indices for ORT 1.24.4. Parsed from
`onnxruntime_c_api.h` lines 1145–7223 (the `struct OrtApi` body).

### Regenerating

When bumping ORT:

```python
import re
hdr = "/opt/homebrew/Cellar/onnxruntime/<ver>/include/onnxruntime/onnxruntime_c_api.h"
with open(hdr) as f:
    lines = f.readlines()
# Find "struct OrtApi {" open and matching "};" close — paste body into body var
pat_api = re.compile(r'ORT_API2_STATUS\(\s*(\w+)\s*,')
pat_release = re.compile(r'ORT_CLASS_RELEASE\(\s*(\w+)\s*\)')
pat_fp = re.compile(r'\(ORT_API_CALL\*\s*(\w+)\s*\)')
# iterate body; for each line try api, release (prefix "Release"), fp in order
# names list index == IDX for that name
```

Then hand-update this JSON and re-run `test_embedder_ort_api_indices.py`.

## s5_1_corpus.jsonl

50-observation corpus + 5 paraphrase queries for the AC4 rerank-recall
test (`tests/test_embedder_real_corpus.py`).

### Structure

- 5 `qN_target`: each has `query` (user-facing paraphrase) and `text`
  (the target observation, different wording from the query)
- 25 `dNN` distractors: keyword-heavy BM25 traps that repeat query
  tokens verbatim
- 20 `nNN` off-topic: noise to fill the corpus to 50

### Dry-run validation (required before editing the fixture)

Before editing `s5_1_corpus.jsonl`, run the BM25-only baseline test:

```
BGE_MODEL_PATH=... ORT_DYLIB_PATH=... python3 -m unittest \
  tests.test_embedder_real_corpus.CorpusBaselineSeededCorrectly -v
```

Each target must sit at BM25 rank 6–10. Rank ≤ 5 means the target has
nothing to gain from rerank; rank > 10 is beyond recall@5's reach. If
seeding is off, adjust distractor wording/count until the baseline is
inside [6, 10] before running the rerank assertion.

## Important

The architect plan's IDX values in `claude-mem-port-s5.1-plan.md` are
from an earlier enumeration and do NOT match the 1.24.4 header. This
JSON is the authoritative oracle. `ort_api_table.py` imports from
this file at module-load time so the two never drift.
