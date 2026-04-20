---
category: decision
---

Bootstrap split into 5 single-responsibility modules rather than one
file with helpers. Driver was the 50-line file limit: each time a new
concern landed (settings patch, path probing, brew install) the file
approached the cap and was extracted. Result: `bootstrap.py` stays a
pure dispatcher (47 lines, all bodies ≤5 lines), and every leaf module
is independently mockable — tests target the specific module under
test (e.g. `embedder._lib.bootstrap_steps.subprocess.run`) not a
monolithic namespace.

---
category: warning
---

The `download-model.sh` NONINTERACTIVE semantics were **inverted** in
this story: previously `NONINTERACTIVE=1` caused exit 2 (abort so
interactive run could be re-initiated); now `NONINTERACTIVE=1` proceeds
without prompting. `CI=1` still aborts with exit 2 (CI should never
silently download large blobs). Two existing tests were updated — any
caller relying on the old "=1 aborts" contract will break silently.

---
category: pattern
---

For modules that touch `~/.claude/settings.json`, introduce a
`CLAUDE_SETTINGS_PATH` env var override. Tests use `patch.dict(
os.environ, {"CLAUDE_SETTINGS_PATH": str(tmppath)}, clear=False)` to
redirect writes to a temp file without touching the user's real
settings. This pattern is now used by `bootstrap_settings.apply()` and
should be followed by any future writer of settings.json.

---
category: fragility
---

`tests/test_bootstrap.py::RunAsModuleInvokesRun` spawns a subprocess
and force-sets `platform.system` to "Linux" inside the child process.
Without forcing non-Darwin, the test outcome depends on the host's
embedder health state (dylib present? model present? settings
patched?). The test is deterministic ONLY because it overrides
platform detection — anyone modifying the test should preserve that
override.

---
category: discovery
---

`code-shape-check.sh` enforces the 50-line file limit but does NOT
enforce the 5-line function body limit (grepped the hook). AC12's
body-limit requirement must be verified by reviewer eye during
review, not by automation. Watch for new contributors landing
7-line function bodies and passing CI.

---
category: discovery
---

Apple Silicon vs Intel brew prefix probing: `bootstrap_paths.py`
iterates `("/opt/homebrew/lib", "/usr/local/lib")` in order, returning
the first hit. On Intel Macs the dylib lives at `/usr/local/lib`; on
Apple Silicon at `/opt/homebrew/lib`. Defaulting to the Apple Silicon
prefix when neither exists (we're writing a "would-be" path for the
partial-bootstrap log line) is the correct choice on modern hardware.
