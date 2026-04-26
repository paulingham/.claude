---
category: discovery
---

Bash 3.2 (macOS default) `exec 3< <(tail -n +1 -f "$LOG")` does NOT yield a usable PID for the tail process via `$!`. The process-substitution PID is the subshell's, not the producer's, and on bash 3.2 it is unreliable to capture for watchdog kill. The working pattern is an explicit FIFO: `mkfifo "$FIFO"; tail ... > "$FIFO" &; TAIL_PID=$!; exec 3< "$FIFO"`. Watchdog `( sleep "$TO"; kill -TERM "$TAIL_PID" ) &` then closes fd 3 cleanly when the timeout fires, breaking the read loop and letting the script reach `exit 124`.

---
category: warning
---

Bash 3.2 silently sets `SIG_IGN` on SIGINT for jobs launched as `&` from a shell that ignores SIGINT (typical of bats/CI). Once a signal is `SIG_IGN` at shell startup, POSIX prohibits `trap` from re-enabling it — so `trap '_aw_on_int' INT` has no effect inside the backgrounded process, and the test that sends `kill -INT $pid` blocks until the script's own timeout fires. T-INT tests must use SIGTERM (which has no such limitation); the script wires INT and TERM to the same trap, so semantics are preserved. Documented inline in `tests/shell/await-pattern.bats` above the SLICE 4 block.

---
category: fragility
---

Under `set -euo pipefail`, an `&&` chain in a cleanup function aborts the script if the right side returns non-zero. Specifically `[ "$WD_PID" -gt 0 ] && kill -TERM "$WD_PID" 2>/dev/null` aborts when the watchdog has already exited (kill returns 1). Every cleanup line MUST end with `|| true` or be wrapped in `{ ... ; } || true` — otherwise the trap-driven exit path is preempted and the wrong status code surfaces. Caught by T2b (expected 124, got 1).

---
category: pattern
---

Test wrappers like `run bash -c "$CMD; echo EXIT=\$?"` always make `$status == 0` because `echo` is the last command in the wrapper. Use `run "$CMD" args...` directly (bats already captures non-zero exit in `$status`) or compare on `$output` if the exit code is intentionally swallowed. Originally tripped T2b — the script was correct but the test was lying.

---
category: decision
---

Chose FIFO + `tail -n +1 -f` over `read -t` polling because the test suite requires both (a) match on dynamically-appended lines (T5) and (b) the read loop to wake up on timeout-driven fd-3 close. Polling would burn CPU and have a sub-second timeout granularity problem; FIFO + watchdog kill is exact.
