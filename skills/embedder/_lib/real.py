"""Real ctypes-backed Embedder. DEFERRED — see build verdict S5 slice 4.

Slice 4 (OrtApi ctypes binding) was halted: the ORT C API is a fixed-offset
function-pointer table with ~250 entries. Declaring only the 12 used entries
produces wrong offsets; declaring all entries exceeds the 50-line budget.
Plan's option (a) (split ort_api.py + ort.py) is insufficient at the offsets.

The FakeEmbedder path (CLAUDE_EMBEDDER=fake) ships today. The real path
raises EmbedderUnavailable, which is surfaced by: AC11 recall banner,
AC13 `embedder doctor`, and AC1/AC2 degraded-mode capture paths.

Next story (S5.1 or S7 Endless Mode) picks up the real backend by either:
- Adopting a shape-override for ort_api.py specifically, OR
- Writing a tiny C shim (no Python PyPI dep; shim is user-installed).
"""
from embedder._lib import paths


def build():
    paths.resolve_dylib()
    paths.resolve_model()
    raise paths.EmbedderUnavailable(
        "Real ORT backend not yet implemented — "
        "set CLAUDE_EMBEDDER=fake or run 'embedder doctor'")
