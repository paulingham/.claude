"""Doctor diagnostic: 6 fields + verdict. See SKILL.md and plan AC13."""
import os
import sys

from embedder import status
from embedder._lib import doctor_db, doctor_probe, doctor_verdict

_FIELDS = ("ORT_DYLIB_PATH", "BGE_MODEL_PATH", "last_error",
           "last_error_at", "last_success_at")


def report():
    if sys.platform == "win32":
        return "platform: windows_not_supported\nverdict: degraded\n"
    st = status.read()
    ok, reason = doctor_probe.probe_facade()
    unembedded = doctor_db.unembedded_count()
    verdict = doctor_verdict.compute(ok, reason, st, unembedded)
    return _render(st, unembedded, verdict)


def _render(st, unembedded, verdict):
    lines = [_line(field, _value(field, st)) for field in _FIELDS]
    lines.append(f"unembedded_count: {unembedded}")
    lines.append(f"verdict: {verdict}")
    return "\n".join(lines) + "\n"


def _value(field, st):
    if field in ("ORT_DYLIB_PATH", "BGE_MODEL_PATH"):
        return os.environ.get(field) or "<unset>"
    return st.get(field) or "<none>"


def _line(key, value):
    return f"{key}: {value}"
