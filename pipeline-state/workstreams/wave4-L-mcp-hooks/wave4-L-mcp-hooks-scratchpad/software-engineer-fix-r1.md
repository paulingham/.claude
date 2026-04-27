---
category: pattern
---

# Wave 4-L Round 1 Fix Engineer — Discoveries

## C1+C2 (REST→gh-CLI shape parity)

**Discovery**: The MCP server prefetch path was writing raw GitHub REST bytes
into `view.json` and `files.txt`. Consumers expected gh-CLI shape (`mergedAt`,
`mergeCommit.oid`, slim labels, newline-delimited filenames). Two wire shapes
inside the same cache silently broke parity.

**Fix**: Extracted reshape logic into `hooks/_lib/github-cache-server-shape.py`
(`reshape_view`, `reshape_files`). Wired in `github-cache-server-fetch.py`
between fetch and write. The H2 e2e bats test
(`tests/shell/wave4l_e2e_rest_to_consumer.bats`) is the cross-module guarantee
— it exercises real REST bytes (urllib monkey-patched via `sitecustomize.py`)
through the real server-write → real consumer-read path. The pre-existing
`pr-fixture/` is the gh-shape; the new `rest-fixture/` is the REST shape.

## H1 (SSRF removal)

**Discovery**: `_owner_repo_from_origin()` previously read `_TEST_GH_OWNER_REPO`
env var as a free-form override; an attacker setting that env var could redirect
HTTP to an arbitrary host. Replaced with a module-level constant
`_GH_API_BASE = "https://api.github.com"` and tests use
`unittest.mock.patch.object` for the seam.

**Pattern**: When code needs a "test-only override" of a security-sensitive
constant, prefer module-level constant + `patch.object` over an env-var hole.
The patch is scoped to the test; the constant is not user-controllable in prod.

## H3 (cache JSON validation)

**Discovery**: Both `ecw_cache_view` (worker filters) and `pr_view_from_cache`
(case-build) trusted the cache file blindly. A malformed `view.json` (bad bytes
on disk, partial write recovered, etc.) would propagate downstream as silent
corruption rather than triggering the gh fallback. Added `_*_validated_json_cat`
helpers using `jq -e .` for structural validation; non-zero exit triggers the
existing fallback path.

**Fragility**: The fallback test `wave4l_worker_graceful_fallback.bats` was
asserting a side-effect that happened to work but for the wrong reason. After
this fix it now passes for the right reason (cache parse failure → fallback).

## M1+M3 (perms hardening + atomic publication)

**Discovery**: Cache files were written with default umask (often 0o644
world-readable) into a path that included no `.tmp` staging. A reader with no
JSON validation would race the writer and read truncated bytes. Combined with
H3 in tests but the underlying fix was independent: write `.tmp`, `os.replace`
to final, `.complete` sentinel last. Dir mode 0o700, file mode 0o600 explicitly
chmod'd post-write (umask cannot be relied on).

**Pattern**: For local cache layouts shared by multiple processes, the
publication contract is `[*.tmp → final via os.replace] × N, then .complete`.
Consumers MUST gate on `.complete`; producers MUST emit it last. This is what
`gh_cache_ready` checks.

## M2 (shared layout)

**Decision**: Made `hooks/_lib/gh-cache-layout.sh` the single source of truth
for the cache directory layout (root resolution, per-PR path, ready check) for
shell consumers. The Python side has its parallel constant in `*-lib.py`. Both
respect `XDG_CACHE_HOME`, `CLAUDE_GH_CACHE_DIR` override, and never default to
`/tmp` (closes the world-writable tempdir CVE class).

## M4 (regex guard)

**Pattern**: For external CLI version strings, use a strict semver regex
(`^[0-9]+\.[0-9]+\.[0-9]+$`) and exit 0 silently on no-match. Lenient parsing
of garbage suffixes (`1.2.3-beta`, `1.2.3rc1`) breaks the comparison and risks
false-warning storms. The `claude --version` output format is upstream-owned;
we exit 0 silently on format drift rather than fighting it.

## M5 (bats helper extraction)

**Pattern**: When 3 helpers (`_install_fail_gh`, `_install_mock_gh_with_fixture`,
`_seed_cache`) are duplicated across 2+ bats files, extract to
`tests/shell/_<feature>_helpers.bash`. The `_` prefix matches the existing
`_cli_shims.bash` / `_conformance_cases.bash` convention. Source-once contract:
caller sets REPO_ROOT/FIXTURE/WORK/PR/CLAUDE_GH_CACHE_DIR/CLAUDE_SESSION_ID,
then sources. parity bats: 131→96 lines.

## Hooks-of-harness fragility

**Warning**: The `main-branch-guard.sh` PreToolUse hook treats `;`-separated
shell one-liners with sensitive verbs as if each clause runs against the
top-level cwd. `cd /tmp/x; git status` is BLOCKED even though semantically
benign. Use `&&` not `;`, or use `git -C "$WORKTREE" ...`.

**Warning**: bats `setup()` running with PYTHONPATH backslash-escaped inside
double quotes (`"$SHIM\${PYTHONPATH:+:\$PYTHONPATH}"`) silently produces a
literal string; the urllib monkey-patch never installs and the test fails with
a real HTTP error. Use unescaped form `"$SHIM${PYTHONPATH:+:$PYTHONPATH}"`.
The H2 test failed for an entire compaction cycle on this single typo.

## Pre-existing test infrastructure issues (out of scope)

**Warning** for next agent: `python3 -m pytest tests/` fails to collect
several files (`test_advisor_resolver`, `test_agent_path_validator`,
`test_bestofn_gate`, `test_contradiction_triggers_plan_update`, etc.) because
there is no `conftest.py` adding `hooks/_lib` to `sys.path`. Workaround:
`PYTHONPATH=hooks/_lib python3 -m pytest tests/`. With the workaround all
845 collected tests pass minus 2 pre-existing unrelated failures
(`test_install_tools::test_shellcheck_clean_if_available` flags an SC2015 in
`scripts/_lib/await-pattern-lib.sh` from wave 2-F2; `test_settings_portability`
flags `env.HCOM=null`). Neither is in wave4-L scope.
