"""HuggingFace BasicTokenizer pipeline orchestrator.

Order: clean_text -> tokenize_cjk -> whitespace_split -> per-word
(strip_accents -> lower -> split_on_punc). Matches
transformers.BertTokenizer(do_lower_case=True) basic stage.
"""
from embedder._lib import tokenizer_clean as clean
from embedder._lib import tokenizer_punc as punc


def basic_tokenize(text):
    cleaned = clean.tokenize_cjk(clean.clean_text(text))
    return [t for w in cleaned.split() for t in _process(w) if t]


def _process(word):
    return punc.split_on_punc(clean.strip_accents(word).lower())
