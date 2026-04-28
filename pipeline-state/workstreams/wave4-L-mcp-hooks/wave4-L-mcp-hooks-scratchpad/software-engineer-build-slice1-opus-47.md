---
category: decision
---

Server is decomposed into 5 modules to honor the 50-line file budget:
`github-cache-server-lib.py` (pure regex/path helpers), `-fetch.py`
(urllib + cache-write I/O), `-prefetch.py` (extract→resolve→fetch→cache
orchestration), `-rpc.py` (JSON-RPC dispatch with closure-injected
deps), and `github-cache-server.py` (entry point + serve loop). All
five files ≤50 lines; all functions ≤5 lines. The plan called for
"~50 lines" for a single server file — that constraint was not
satisfiable with `_extract_pr`, `_extract_owner_repo`,
`_fetch_pr_data`, `_write_cache`, JSON-RPC dispatch, AND env guards
all in one file. Splitting kept every helper testable in isolation
and made dependency injection explicit in `make_dispatch(lib, fetch,
prefetch)`.

---
category: discovery
---

The TDD guard hook (`hooks/tdd-guard.sh`) maps source paths to test
paths by simple replacement: `hooks/_lib/foo-bar.py` →
`tests/test_foo-bar.py` (preserving hyphens). The existing test suite
has files like `test_advisor_resolver.py` (underscores everywhere),
so the guard's hyphen-preservation behavior was a surprise. To
satisfy the guard for each new module I wrote a per-module test file
with the hyphenated name; collectively they double as the smaller
unit-of-work tests the plan calls for. Net result: more granular
test coverage than the plan's single-file pytest suite required.

---
category: warning
---

`urllib.request.urlopen` is monkey-patched globally in tests via
`mock.patch("urllib.request.urlopen", side_effect=...)`. Modules in
this PR import `urllib.request` at module load and call
`urllib.request.urlopen(...)` at request time, which honors the
patch. Reviewers verifying behavior should NOT refactor to
`from urllib.request import urlopen` (binding at import time would
break the mock-based tests).

---
category: pattern
---

`_TEST_GH_API_BASE` is read inside `_api_base()` which is called by
`_do_fetch()` at request time. `os.environ.get(...)` is NOT cached
into a module-level constant. This is required by AC8: "set env
after import, then call → URL changes". Same pattern applies to
`GITHUB_PERSONAL_ACCESS_TOKEN` (read inside `_open` and `fetch_pr_data`
guard) and `CLAUDE_GH_CACHE_DIR` (read inside `cache_dir_for`).

---
category: fragility
---

`extract_owner_repo` rejects URLs with embedded slashes inside
{owner} or {repo} (the regex uses `[^/]+`). Self-hosted GHE URLs
like `https://ghe.acme.com/...` are deliberately rejected as
"unsupported remote" per Risk #6 in the plan. If we ever need to
support GHE, both the regex AND `_api_base()` need updating
together — they are coupled through the assumption that the
GitHub host is `api.github.com`.
