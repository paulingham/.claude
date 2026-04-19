"""Mean pool over masked tokens, L2 normalise, pack as little-endian float32."""
import math
import struct

_DIM = 384


def mean_pool_l2(raw, seq_len, mask):
    mean = _masked_mean(raw, seq_len, mask)
    norm = math.sqrt(sum(x * x for x in mean))
    normed = [0.0] * _DIM if norm == 0 else [x / norm for x in mean]
    return struct.pack(f"<{_DIM}f", *normed)


def _masked_mean(raw, seq_len, mask):
    denom = sum(mask) or 1
    return [_dim_sum(raw, seq_len, mask, d) / denom for d in range(_DIM)]


def _dim_sum(raw, seq_len, mask, d):
    return sum(raw[t * _DIM + d] for t in range(seq_len) if mask[t])
