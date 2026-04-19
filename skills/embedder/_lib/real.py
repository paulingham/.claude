"""Real ctypes+ORT-backed Embedder. Builds once, caches api+session handle."""
from embedder._lib import (model_io, ort_api, ort_dispatch, ort_session,
                           ort_session_run, paths, pool, tokenizer)

_DIM = 384


def build():
    api = ort_api.load_api(paths.resolve_dylib())
    handle = ort_session.build(api, paths.resolve_model())
    return RealEmbedder(api, handle)


class RealEmbedder:
    def __init__(self, api, handle):
        self._api, self._handle = api, handle

    def encode(self, text, max_len=128):
        """Text -> tokenize -> ORT Run -> read fp32 -> mean-pool-L2 -> bytes."""
        ids, mask, types_ = tokenizer.encode(text, max_len=max_len)
        output = ort_session_run.run(self._handle, ids, mask, types_)
        try:
            raw = model_io.read_float32_data(self._api, output, max_len * _DIM)
        finally:
            ort_dispatch.call(self._api, "ReleaseValue", output)
        return pool.mean_pool_l2(raw, max_len, mask)

    def close(self):
        ort_session.close(self._handle)
