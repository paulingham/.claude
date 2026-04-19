# Tokenizer Fixtures

## mini_vocab.txt (124 tokens)

Synthetic mini-vocab for Slice 1 WordPiece algorithm tests. Structure
mirrors BertTokenizer: `[PAD]=0`, `[unused1..99]`, `[UNK]=100`,
`[CLS]=101`, `[SEP]=102`, `[MASK]=103`, then known tokens + WordPiece
suffixes (`##ing`, `##s`, etc.).

This fixture proves the algorithm is correct against hand-computed
ids. It is NOT the production bge vocab.

## vocab.txt (30522 tokens) — NOT COMMITTED

The real bge-small-en-v1.5 vocab. Produced by:

```bash
curl -fsSL -o skills/embedder/vocab/vocab.txt \
  'https://huggingface.co/BAAI/bge-small-en-v1.5/resolve/main/vocab.txt'
wc -l skills/embedder/vocab/vocab.txt   # expect 30522
```

S5.1 build deferred the download: the build environment blocks egress
to huggingface.co. Committing the real vocab is a **prerequisite to
using the real embedder end-to-end**. Until committed, setting
`ORT_DYLIB_PATH` + `BGE_MODEL_PATH` will fail loading the tokenizer at
runtime. The algorithm is proven correct via mini_vocab tests.

## reference-tokens.json (10 cases) — NOT COMMITTED

Pre-computed `{"input": str, "ids": [int, ...]}` byte-exact parity
oracle. Produced via a throwaway venv:

```bash
python3 -m venv /tmp/venv && /tmp/venv/bin/pip install transformers
/tmp/venv/bin/python - <<'PY'
import json
from transformers import AutoTokenizer
tok = AutoTokenizer.from_pretrained("BAAI/bge-small-en-v1.5")
cases = ["hello world", "the cat sat on the mat", "embedder tokenizer test",
         "run 42", "", "Mixed Case Text", "emoji 🚀 fire", "tab\\ttab",
         "very long text " * 30, "CJK 你好世界"]
out = [{"input": c, "ids": tok.encode(c, max_length=512, truncation=True,
        padding="max_length")} for c in cases]
print(json.dumps(out, indent=2))
PY
```

Same reason as vocab: build env lacks network + pip.
