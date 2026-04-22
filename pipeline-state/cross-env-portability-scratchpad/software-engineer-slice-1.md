---
category: discovery
---

New modular boundary: `scripts/_lib/detect-ort.sh` is the canonical OS-aware
ORT library resolver, sibling of `detect-os.sh`. It respects `ORT_DYLIB_PATH`
override first, then probes per-OS candidate paths. Tests override
`ORT_CANDIDATE_PATHS` to stay hermetic. Python has a parallel resolver in
`skills/embedder/_lib/bootstrap_paths.py` that must agree on the override
file — enforced by `tests/test_ort_path_integration.py`.

---
category: pattern
---

OS dispatch is extracted to its own module (`bootstrap_install.py`, 15 lines)
rather than inlined into `bootstrap_steps.py`. This (a) keeps shape under
50 lines, (b) provides a clean patch target for tests
(`embedder._lib.bootstrap_install.platform.system`), and (c) makes the
dispatch table discoverable. Repeat this split whenever a consumer module
grows OS-awareness.

---
category: pattern
---

`cli_setup_text.py` holds per-OS setup strings; `cli_actions.py` just
dispatches. Tests patch `embedder._lib.cli_setup_text.platform.system` to
force a branch. Single-responsibility split keeps both files under 40
lines and keeps the patch target obvious.

---
category: warning
---

Shellcheck SC1091 fires on `source "$(dirname "${BASH_SOURCE[0]}")/..."`
because shellcheck can't statically resolve the path. Requires both
`# shellcheck source=<relative-path>` AND `# shellcheck disable=SC1091`
(or run with `shellcheck -x`). `tests/test_install_tools.py` runs
shellcheck without `-x`, so the disable comment is required for any new
runtime-sourced script to keep the static-check test green.

---
category: fragility
---

Pre-existing failures NOT from this slice:
- `bats tests/shell/settings-portability.bats` AC2.4 (env.HF_TOKEN_PATH=null)
  and AC2.7 (HF_TOKEN value unchanged) — introduced by PR #17 when HF_TOKEN
  was removed from `settings.json`. The test file still asserts on these
  keys. Either the assertions or the settings file need reconciliation.
  Out of scope for cross-env portability slice 1.

---
category: decision
---

Kept `SETUP_TEXT` as a back-compat alias in `cli_setup_text.py` and
re-exported it from `cli_actions.py`. Reason: the old constant is
referenced by `tests/test_embedder_cli.py:SetupCommandPrintsInstructions`
and may be imported by external readers. Removing it would be a breaking
change unrelated to this slice's scope.

---
category: decision
---

`bootstrap.WIN_UNSUPPORTED` replaces `SKIP_NON_MACOS`; both names are kept
as aliases because existing bootstrap tests reference the old constant.
macOS + Linux now both run through `_bootstrap()`; only Windows hits the
skip path. `tests/test_bootstrap.py:RunAsModuleInvokesRun` was updated to
force `platform.system='Windows'` to exercise the skip branch.
