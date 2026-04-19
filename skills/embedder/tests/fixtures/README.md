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

See the corpus README (populated in Slice 8).

## Important

The architect plan's IDX values in `claude-mem-port-s5.1-plan.md` are
from an earlier enumeration and do NOT match the 1.24.4 header. This
JSON is the authoritative oracle. `ort_api_table.py` imports from
this file at module-load time so the two never drift.
