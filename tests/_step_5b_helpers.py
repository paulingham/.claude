"""Shared helpers for `tests/test_build_step_5b_*.py`.

`_step_5b_body(text)` slices the substring of `skills/build-implementation/SKILL.md`
spanning the Step 5b heading up to (but not including) the next top-level
(`## `) heading. Returns empty string when Step 5b is absent so tests can
fail with a clear "heading not found" message instead of crashing on a
None slice.

The slice is a heading-text slice, NOT a code-block-aware slice — a line
inside a fenced code block that starts with `## ` would terminate the
body. Callers must not embed `## ` headings inside Step 5b's code blocks
or the body window will collapse early.
"""


def step_5b_body(text):
    lines = text.splitlines(keepends=True)
    start_idx = -1
    for idx, line in enumerate(lines):
        stripped = line.rstrip()
        if (stripped.startswith("### Step 5b:")
                or stripped.startswith("## Step 5b:")):
            start_idx = idx
            break
    if start_idx == -1:
        return ""
    end_idx = len(lines)
    for idx in range(start_idx + 1, len(lines)):
        if lines[idx].rstrip().startswith("## "):
            end_idx = idx
            break
    return "".join(lines[start_idx:end_idx])
