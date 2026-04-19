"""Whitelist filter resolution for observation and scratchpad scopes."""

_OBS_KEYS = ("session_id", "project_hash", "tool", "agent_role", "phase",
             "time_from", "time_to")
_SP_KEYS = ("task_id", "category", "agent_role", "phase",
            "time_from", "time_to")
_WHITELIST = {"observations": _OBS_KEYS, "scratchpad": _SP_KEYS}
_TIME_COLS = {"time_from": ("timestamp", ">="),
              "time_to": ("timestamp", "<=")}


def resolve(source, spec):
    allowed = _WHITELIST[source]
    bad = [k for k in (spec or {}) if k not in allowed]
    if bad:
        raise ValueError(f"unknown filter keys: {bad}")
    return _compile(spec or {})


def _compile(spec):
    frags, params = [], []
    for key, val in spec.items():
        frag, bind = _fragment(key, val)
        frags.append(frag)
        params.append(bind)
    return " ".join(f"AND {f}" for f in frags), tuple(params)


def _fragment(key, val):
    if key in _TIME_COLS:
        col, op = _TIME_COLS[key]
        return f"{col} {op} ?", val
    return f"{key} = ?", val
