---
category: decision
---
Implemented `hooks/no-shell-read.sh` as a thin top-level (28 lines, no functions) plus two helper files in `hooks/_lib/` (`-helpers.sh` and `-path.sh`, both ≤47 lines). Splitting parsing from path-resolution kept every file under the 50-line shape limit and every function body ≤5 lines without sacrificing readability — the alternative (a single 70-line helpers file) blew the limit.

---
category: discovery
---
Clause splitting on `&&|||;|` requires normalising `&&`/`||` to `;` BEFORE splitting on `|` and `;`, otherwise `a || b` becomes three clauses including an empty middle. Used `sed` to normalise then `awk` `gsub` for the final split — keeps it bash-3.2 safe. Streaming detection (`tail -f`/`-F`) runs in the same per-clause loop with an early-allow so that `tail -f log/development.log` is allowed even though it is inside REPO_ROOT.

---
category: warning
---
Path resolution uses `( cd "$dir" 2>/dev/null && pwd )` (POSIX-safe; macOS-compatible). Critical: a relative path whose dirname does not exist on disk resolves to empty → treated as "outside repo" → allowed. This is acceptable for `head/cat/tail` — if the file does not exist the underlying command will fail anyway. Do NOT switch to `realpath` (not available on macOS by default).
