"""Slice 5d: RealEmbedder.encode wires tokenizer → run → read → pool → bytes."""
import struct
import sys
import types
import unittest
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[1]
_SKILL = str(REPO_ROOT / "skills")
if _SKILL not in sys.path:
    sys.path.insert(0, _SKILL)


class EncodeProducesPooledBytes(unittest.TestCase):
    def test_encode_returns_1536_bytes_from_pool(self):
        from embedder._lib import real
        out = _invoke_encode(real, max_len=4)
        self.assertEqual(len(out), 1536)

    def test_encode_passes_max_len_through_tokenizer(self):
        from embedder._lib import real
        calls = _invoke_encode(real, max_len=8, return_calls=True)
        self.assertEqual(calls["tokenizer_max_len"], 8)


def _invoke_encode(real, max_len, return_calls=False):
    calls = {}
    with _patches(real, calls, max_len):
        embedder = real.RealEmbedder("api", _fake_handle(), vocab={"[UNK]": 100})
        out = embedder.encode("hello", max_len=max_len)
    return calls if return_calls else out


def _patches(real, calls, max_len):
    ctx = _StackedPatch()
    ctx.add(mock.patch.object(real, "tokenizer",
                              encode=_fake_tokenizer(calls, max_len)))
    ctx.add(mock.patch.object(real, "ort_session_run",
                              run=mock.Mock(return_value="out_tensor")))
    ctx.add(mock.patch.object(real, "model_io",
                              read_float32_data=mock.Mock(
                                  return_value=[0.0] * (max_len * 384))))
    ctx.add(mock.patch.object(real, "ort_dispatch", call=mock.Mock()))
    ctx.add(mock.patch.object(real, "pool",
                              mean_pool_l2=mock.Mock(
                                  return_value=struct.pack("<384f",
                                                           *([0.0] * 384)))))
    return ctx


def _fake_tokenizer(calls, max_len):
    def encode(text, max_len=128, vocab=None):
        calls["tokenizer_max_len"] = max_len
        return [0] * max_len, [0] * max_len, [0] * max_len
    return encode


def _fake_handle():
    return types.SimpleNamespace(api="api", session="sess", mem_info="mem")


class EncodeReleasesOutputWhenReadRaises(unittest.TestCase):
    def test_release_called_even_when_read_float32_raises(self):
        from embedder._lib import real
        release_count = [0]
        with _patches_read_failure(real, release_count):
            embedder = real.RealEmbedder("api", _fake_handle(), vocab={"[UNK]": 100})
            with self.assertRaises(RuntimeError):
                embedder.encode("hi", max_len=4)
        self.assertEqual(release_count[0], 1)


def _patches_read_failure(real, release_count):
    ctx = _StackedPatch()
    ctx.add(mock.patch.object(real, "tokenizer",
                              encode=lambda t, max_len, vocab=None: (
                                  ([0] * max_len,) * 3)))
    ctx.add(mock.patch.object(real, "ort_session_run",
                              run=mock.Mock(return_value="out_tensor")))
    ctx.add(mock.patch.object(real, "model_io",
                              read_float32_data=mock.Mock(
                                  side_effect=RuntimeError("read boom"))))
    ctx.add(mock.patch.object(real, "ort_dispatch",
                              call=_record_release(release_count)))
    ctx.add(mock.patch.object(real, "pool", mean_pool_l2=mock.Mock()))
    return ctx


def _record_release(counter):
    def call(api, op, *args):
        if op == "ReleaseValue":
            counter[0] += 1
    return call


class VocabResolvedOnceAtInit(unittest.TestCase):
    def test_encode_does_not_call_tokenizer_vocab_load(self):
        from embedder._lib import real, tokenizer_vocab
        with mock.patch.object(tokenizer_vocab, "load",
                               side_effect=AssertionError("should not load")):
            embedder = _build_with_preloaded_vocab(real)
            with _patches_happy_path(real):
                embedder.encode("hi", max_len=4)


def _build_with_preloaded_vocab(real):
    return real.RealEmbedder("api", _fake_handle(), vocab={"[UNK]": 100})


def _patches_happy_path(real):
    ctx = _StackedPatch()
    ctx.add(mock.patch.object(real, "ort_session_run",
                              run=mock.Mock(return_value="out")))
    ctx.add(mock.patch.object(real, "model_io",
                              read_float32_data=mock.Mock(
                                  return_value=[0.0] * (4 * 384))))
    ctx.add(mock.patch.object(real, "ort_dispatch", call=mock.Mock()))
    ctx.add(mock.patch.object(real, "pool",
                              mean_pool_l2=mock.Mock(return_value=b"\x00" * 1536)))
    return ctx


class _StackedPatch:
    def __init__(self):
        self._patches = []

    def add(self, p):
        self._patches.append(p)

    def __enter__(self):
        for p in self._patches:
            p.start()
        return self

    def __exit__(self, *_):
        for p in reversed(self._patches):
            p.stop()


if __name__ == "__main__":
    unittest.main()
