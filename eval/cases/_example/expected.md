# Example Case — Expected Behaviors

Lists the specific behaviors + oracle tests that MUST pass on the candidate's diff for
this case to count as `passed`. Used by the `test-passing` scoring mode (default) to
validate candidate output without requiring byte-equivalent diffs.

## Required behaviors (example)

1. `greet("Ada")` returns `"Hello, Ada!"`
2. `greet(42)` throws `TypeError`
3. `greet("")` throws `RangeError`

## Required oracle tests (green post-change)

These are the exact test names (or node IDs) that MUST be green when the harness runs
the candidate's diff through the repo's test runner. At least one test name per
behavior above.

- `lib/greeter.test.js > greet > returns hello for non-empty name`
- `lib/greeter.test.js > greet > rejects non-string input`
- `lib/greeter.test.js > greet > rejects empty string`

## Notes on authorship

The `/internal-eval capture` command auto-extracts this list from the PR's test-file
changes (see `capture/oracle-paths.json` allow-list in Story 4). For manual cases,
copy the real test names from the merged PR so they match exactly.
