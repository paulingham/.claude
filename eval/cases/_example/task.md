# Example Case — Task Description

This is a **schema example**, not a real case. It shows what `task.md` should contain
when you author a real eval case.

## Purpose of `task.md`

Describe the work to be done in acceptance-criterion form, as if you were handing the
task to a build agent. **Do not** include any hints about the final diff, file paths to
edit, or implementation strategy — those would bias the candidate model.

## Example content (replace with real ACs for your case)

Implement a function `greet(name)` in `lib/greeter.js` that:

1. Returns `"Hello, {name}!"` for any non-empty string `name`.
2. Throws `TypeError` if `name` is not a string.
3. Throws `RangeError` if `name` is an empty string.

## What NOT to include

- File paths beyond those already named by the ACs
- References to functions/classes that must exist post-change (beyond the ACs)
- "Look at file X for the pattern" — the candidate must discover patterns itself
- Snippets of the expected implementation
