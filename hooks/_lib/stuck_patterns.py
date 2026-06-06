"""
Five stuck-detection pattern predicates, extracted from stuck-detector.py.
Each function takes `events: list[dict]` and returns evidence dict or None.
"""

import json
import re

# Pattern-5 context-window marker regex.
# Fragility note: this regex matches Claude Code's observed error text for context/window
# exhaustion. The exact message is not documented in Claude Code public docs; this pattern
# is derived from observed transcript samples. May need updating if the error text changes.
_CONTEXT_WINDOW_RE = re.compile(
    r"context.{0,20}(window|limit|exceeded)|compact",
    re.IGNORECASE,
)

# Volatile keys stripped before action equality comparison
_VOLATILE_KEYS = frozenset({"id", "tool_use_id", "caller", "caller_id", "timestamp"})


def strip_volatile(d: dict) -> dict:
    """Remove volatile keys from a dict (shallow)."""
    return {k: v for k, v in d.items() if k not in _VOLATILE_KEYS}


def eq_no_pid(a: dict, b: dict) -> bool:
    """Equality ignoring volatile ids/timestamps."""
    if a.get("kind") != b.get("kind"):
        return False
    kind = a["kind"]
    if kind == "action":
        return a.get("name") == b.get("name") and a.get("input") == b.get("input")
    if kind == "observation":
        return a.get("content") == b.get("content") and a.get("is_error") == b.get("is_error")
    if kind == "message":
        return a.get("text") == b.get("text")
    return False


def _actions(events: list) -> list:
    return [e for e in events if e["kind"] == "action"]


def _observations(events: list) -> list:
    return [e for e in events if e["kind"] == "observation"]


def _messages(events: list) -> list:
    return [e for e in events if e["kind"] == "message"]


def _all_equal(items: list) -> bool:
    if not items:
        return False
    return all(eq_no_pid(items[0], x) for x in items[1:])


def check_repeating_action_observation(events: list) -> dict | None:
    """Pattern 1: last 4 actions equal AND last 4 observations equal."""
    acts = _actions(events)
    obs = _observations(events)
    if len(acts) < 4 or len(obs) < 4:
        return None
    if _all_equal(acts[-4:]) and _all_equal(obs[-4:]):
        return {"actions": acts[-4:], "observations": obs[-4:]}
    return None


def check_repeating_action_error(events: list) -> dict | None:
    """Pattern 2: last 3 actions equal AND last 3 obs all is_error==true."""
    acts = _actions(events)
    obs = _observations(events)
    if len(acts) < 3 or len(obs) < 3:
        return None
    last_obs = obs[-3:]
    if _all_equal(acts[-3:]) and all(o["is_error"] for o in last_obs):
        return {"actions": acts[-3:], "observations": last_obs}
    return None


def _rindex_event(events: list, target: dict, start_after: int = -1) -> int:
    """Return index of first occurrence of target (by eq_no_pid) after start_after."""
    for i, e in enumerate(events):
        if i > start_after and eq_no_pid(e, target):
            return i
    return -1


def _msg_indices(events: list) -> list:
    """Return indices in events of all message-kind entries."""
    return [i for i, e in enumerate(events) if e["kind"] == "message"]


def check_monologue(events: list) -> dict | None:
    """Pattern 3: last 3 agent messages identical, no observation between them."""
    idxs = _msg_indices(events)
    if len(idxs) < 3:
        return None
    last3_idxs = idxs[-3:]
    last3 = [events[i] for i in last3_idxs]
    if not _all_equal(last3):
        return None
    between = events[last3_idxs[0] + 1:last3_idxs[-1]]
    if any(e["kind"] == "observation" for e in between):
        return None
    return {"messages": last3}


def check_alternating(events: list) -> dict | None:
    """Pattern 4: a0==a2==a4, a1==a3==a5 AND o0==o2==o4, o1==o3==o5."""
    acts = _actions(events)
    obs = _observations(events)
    if len(acts) < 6 or len(obs) < 6:
        return None
    a, o = acts[-6:], obs[-6:]
    if (_all_equal([a[0], a[2], a[4]]) and _all_equal([a[1], a[3], a[5]])
            and _all_equal([o[0], o[2], o[4]]) and _all_equal([o[1], o[3], o[5]])):
        return {"actions": a, "observations": o}
    return None


def _is_context_obs(event: dict) -> bool:
    return event["kind"] == "observation" and bool(
        _CONTEXT_WINDOW_RE.search(event.get("content", ""))
    )


def _longest_context_obs_run(events: list) -> int:
    """Count the longest run of consecutive context-window observations."""
    best = current = 0
    for e in events:
        if _is_context_obs(e):
            current += 1
            best = max(best, current)
        else:
            current = 0
    return best


def check_context_window(events: list) -> dict | None:
    """Pattern 5: >= 10 consecutive context-window observations."""
    run = _longest_context_obs_run(events)
    if run >= 10:
        return {"consecutive_context_obs": run}
    return None
