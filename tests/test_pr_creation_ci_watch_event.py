"""AC3-AC4-quat: Prose-contract assertions for the upgraded §5b event-stream CI-watch.

These tests verify that skills/pr-creation/SKILL.md §5b describes a Monitor
event-stream subscription (not a busy-poll loop) while preserving all existing
keyword pins tested in test_pr_creation_ci_watch.py (AC5-AC12 there).
"""
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SKILL = REPO_ROOT / "skills" / "pr-creation" / "SKILL.md"


def _skill_text():
    return SKILL.read_text()


def _step5b_section(text):
    """Extract the CI-watch section between Step 5 and Step 6."""
    m = re.search(
        r"(### 5b\..+?)(?=\n### 6\.|\Z)",
        text,
        re.DOTALL,
    )
    return m.group(1) if m else None


def test_step5b_describes_event_stream_not_busy_poll():
    """AC3: §5b prose names Monitor event-stream + 'one line per concluded run'
    + 'silence is not success'; the busy-poll framing is gone; gh pr checks
    (RED-path --log-failed) and git ls-remote survive.
    """
    text = _skill_text()
    section = _step5b_section(text)
    assert section is not None, "No ### 5b. section found"

    # Must name an event-stream / Monitor subscription (not a polling loop)
    event_stream_present = any(
        kw in section
        for kw in (
            "event-stream",
            "event stream",
            "Monitor",
            "monitor",
            "event subscription",
        )
    )
    assert event_stream_present, (
        "§5b must describe a Monitor event-stream subscription, not a polling loop. "
        "Expected one of: 'event-stream', 'Monitor', 'event stream', 'event subscription'."
    )

    # Must name "one line per concluded run" semantics
    one_line_per_run = any(
        kw in section
        for kw in (
            "one line per concluded run",
            "one structured line per concluded",
            "one event line per concluded",
            "emits one line per",
        )
    )
    assert one_line_per_run, (
        "§5b must state 'one line per concluded run' (or equivalent) to document "
        "the event cardinality — one structured line per concluded CI run."
    )

    # Must name "silence is not success"
    assert "silence is not success" in section, (
        "§5b must contain 'silence is not success' to document that the "
        "absence of Monitor events does not constitute a green signal."
    )

    # Old busy-poll framing at the arm step must be gone
    busy_poll_framing = "Poll `gh pr checks" in section and "in a loop" in section
    assert not busy_poll_framing, (
        "§5b must NOT contain the busy-poll framing "
        "'Poll `gh pr checks ... in a loop' — this phrasing was removed "
        "when the mechanism was upgraded to Monitor event-stream."
    )

    # gh pr checks must still survive (RED-path --log-failed occurrence)
    assert "gh pr checks" in section, (
        "§5b must still contain 'gh pr checks' — the RED-path "
        "'gh pr checks \"$PR\" --log-failed' occurrence must be preserved."
    )

    # git ls-remote must survive (re-arm SHA verification)
    assert "git ls-remote" in section, (
        "§5b must still contain 'git ls-remote' — the re-arm SHA verification step."
    )


def test_failure_event_triggers_notify_and_cancel_window():
    """AC4: RED-hint path names PushNotification + notify+cancel window before
    fix-loop re-entry, reusing watch-skipped:operator-cancel.
    """
    text = _skill_text()
    section = _step5b_section(text)
    assert section is not None, "No ### 5b. section found"

    # Must name PushNotification (or push notification) for the RED-hint path
    push_notification_present = any(
        kw in section
        for kw in (
            "PushNotification",
            "push notification",
            "Push notification",
        )
    )
    assert push_notification_present, (
        "§5b RED-hint path must name a PushNotification to alert the operator "
        "before re-entering the fix loop."
    )

    # Must name a notify+cancel window
    cancel_window_present = any(
        kw in section
        for kw in (
            "notify",
            "cancel window",
            "notification window",
            "cancellation window",
        )
    )
    assert cancel_window_present, (
        "§5b RED-hint path must name a notify+cancel window before fix-loop re-entry "
        "(conservative autonomy — operator gets a window to intervene)."
    )

    # Must still name watch-skipped:operator-cancel (operator cancel reuse)
    assert "watch-skipped:operator-cancel" in section, (
        "§5b RED-hint cancel path must reuse 'watch-skipped:operator-cancel' "
        "as the verdict string when the operator cancels within the window."
    )


def test_step5b_names_monitor_silence_deadline_with_mechanism():
    """AC4-bis: §5b mandates a Monitor silence deadline with a NAMED enforcement
    mechanism AND a concrete default floor; silence past budget → watch-skipped,
    never an unbounded block.
    """
    text = _skill_text()
    section = _step5b_section(text)
    assert section is not None, "No ### 5b. section found"

    # Must name a silence deadline mechanism
    silence_deadline_present = any(
        kw in section
        for kw in (
            "silence deadline",
            "silence budget",
            "silence-deadline",
            "silence_deadline",
            "timeout_ms",
            "bounded deadline",
            "silence past",
        )
    )
    assert silence_deadline_present, (
        "§5b must name a Monitor silence deadline mechanism (e.g. 'timeout_ms', "
        "'bounded deadline', 'silence budget') — the orchestrator must not block "
        "indefinitely if the Monitor emits no events."
    )

    # Must name what happens when silence budget is exceeded: watch-skipped
    silence_routes_to_watch_skipped = any(
        kw in section
        for kw in (
            "silence past",
            "silence budget → watch-skipped",
            "past the budget",
            "past the silence",
            "silence → watch-skipped",
        )
    )
    assert silence_routes_to_watch_skipped or "watch-skipped" in section, (
        "§5b must state that silence past the budget routes to watch-skipped, "
        "never an unbounded block."
    )

    # Must provide a concrete default floor (a number or 'default floor')
    has_concrete_floor = any(
        kw in section
        for kw in (
            "default floor",
            "concrete default",
            "minutes",
            "seconds",
            "ms",
            "timeout",
        )
    )
    assert has_concrete_floor, (
        "§5b must provide a concrete default floor for the silence deadline "
        "(e.g. 'default floor: 30 minutes', a timeout_ms value, etc.)."
    )


def test_step5b_green_decision_routes_through_ci_status_decision():
    """AC4-ter: §5b prose states the GREEN decision is NOT made on the event alone —
    a candidate-green event triggers an authoritative ci_status_decision(PR)
    re-check before CI_GREEN is emitted.
    """
    text = _skill_text()
    section = _step5b_section(text)
    assert section is not None, "No ### 5b. section found"

    # Must name ci_status_decision as the authoritative GREEN decider
    ci_status_decision_present = any(
        kw in section
        for kw in (
            "ci_status_decision",
            "ci_status_decision(PR)",
        )
    )
    assert ci_status_decision_present, (
        "§5b must name ci_status_decision(PR) as the authoritative GREEN decider. "
        "A candidate-green event from the Monitor must trigger a live re-check via "
        "ci_status_decision before CI_GREEN is emitted."
    )

    # Must state the event alone does NOT decide GREEN
    not_event_alone = any(
        kw in section
        for kw in (
            "not made on the event alone",
            "event alone",
            "authoritative GREEN",
            "candidate-green event triggers",
            "candidate-green → ci_status_decision",
        )
    )
    assert not_event_alone, (
        "§5b must state the GREEN decision is not made on the event alone — "
        "a candidate-green event triggers an authoritative re-check."
    )


def test_step5b_names_awaiting_first_event_status_and_latency_signal():
    """AC4-quat: §5b names an operator-visible 'awaiting first CI event' status
    AND records the success signal: re-entry latency drops from poll-interval to
    time-of-failure-event.
    """
    text = _skill_text()
    section = _step5b_section(text)
    assert section is not None, "No ### 5b. section found"

    # Must name an "awaiting first CI event" status (or equivalent)
    awaiting_status_present = any(
        kw in section
        for kw in (
            "awaiting first CI event",
            "awaiting first event",
            "waiting for first CI event",
            "CI-watch armed",
        )
    )
    assert awaiting_status_present, (
        "§5b must name an operator-visible 'awaiting first CI event' status "
        "(or 'CI-watch armed' equivalent) so the silence window is not a blind wedge "
        "— the operator can see the subscription is active."
    )

    # Must record the latency success signal
    latency_signal_present = any(
        kw in section
        for kw in (
            "latency",
            "time-of-failure-event",
            "time of failure",
            "poll-interval",
            "poll interval",
        )
    )
    assert latency_signal_present, (
        "§5b must name the latency improvement: re-entry latency drops from "
        "poll-interval to time-of-failure-event (the success signal)."
    )
