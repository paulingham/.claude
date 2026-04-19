# Tokenizer Fixtures

## mini_vocab.txt (124 tokens)

Synthetic mini-vocab for Slice 1 WordPiece algorithm tests. Structure
mirrors BertTokenizer: `[PAD]=0`, `[unused1..99]`, `[UNK]=100`,
`[CLS]=101`, `[SEP]=102`, `[MASK]=103`, then known tokens + WordPiece
suffixes (`##ing`, `##s`, etc.).

This fixture proves the algorithm is correct against hand-computed
ids. It is NOT the production bge vocab.

## vocab.txt (30522 tokens) — committed at `skills/embedder/vocab/vocab.txt`

The real bge-small-en-v1.5 vocab. Originally sourced from:

```bash
curl -fsSL -o skills/embedder/vocab/vocab.txt \
  'https://huggingface.co/BAAI/bge-small-en-v1.5/resolve/main/vocab.txt'
wc -l skills/embedder/vocab/vocab.txt   # 30522
```

Committed during S5.1 fix (CRITICAL C1). The tokenizer loads it at
`RealEmbedder` construction time and caches the `{token: id}` dict.

## reference-tokens.json (10 cases) — committed at `skills/embedder/tests/fixtures/reference-tokens.json`

Pre-computed `{"input": str, "input_ids": [...], "attention_mask":
[...], "token_type_ids": [...], "tokens": [...]}` byte-exact parity
oracle. See `skills/embedder/tests/fixtures/README.md` for case list
and regeneration recipe. Consumer:
`tests/test_tokenizer_reference.py`.
