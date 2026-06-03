# Agent Protocol

Content every agent (subagent or teammate) needs at spawn time. The iron laws governing orchestrator/agent boundaries live in `rules/core.md`. Orchestrator-side decision logic and lifecycle management lives in `~/.claude/orchestrator/agent-orchestration.md`.

## Isolation: Worktrees and Branches

You (the agent) are spawned into one of two modes — the orchestrator's spawn prompt tells you which:

- **Worktree** (write-capable subagent phases). The path is passed in your prompt as `Working directory: <path>`. All writes and git commands target this worktree. Write-capable roles: `software-engineer`, `frontend-engineer`, `qa-engineer`, `database-engineer`, `infrastructure-engineer`.
- **Feature branch** in the pipeline team (team phase teammate). You create your own branch (e.g., `build/{task-id}-{slice}`) and commit there before completing.

Read-only roles (`code-reviewer`, `security-engineer`, `product-reviewer`, `architect`) work without a worktree.

## Commit Protocol

All agents (subagents in worktrees AND teammates on branches) MUST commit before completing:
1. Stage all changed files: `git add` specific files (not `git add .`)
2. Commit with a descriptive message including: what was built, test count, any known issues
3. If work is incomplete (approaching turn limit): commit with `WIP:` prefix
4. The orchestrator merges branches via `git merge` or `git cherry-pick`
5. Never leave uncommitted changes -- uncommitted work cannot be merged reliably

## Hooks Calling MCP

A `PostToolUse` matcher block may contain multiple hook entries. Two hook types
coexist there: `command` (shell) and `mcp_tool` (JSON-RPC into a registered
MCP server in `mcpServers`). They run **in parallel**, not in sequence — the
hook runner does not chain `mcp_tool` output to a subsequent `command`.

Pattern: when a `command` hook needs data that an `mcp_tool` would expose, do
NOT try to wire one to the other. Instead, have the MCP server **write a
cache file** (or other side-effect on the local filesystem) that the sibling
`command` hook reads after a brief poll. The two hooks observe each other
through the filesystem, not through the hook runner.

Worked example (Wave 4-L `gh-cache`):

- `command` hook spawns the eval-capture worker (`nohup ... & disown`).
- `mcp_tool` hook calls `prefetch_pr` on the `gh-cache` server with the
  bash command string as input. The server extracts the PR number, fetches
  view/diff/files via `urllib.request`, and writes
  `${CLAUDE_GH_CACHE_DIR}/<session>-<pr>/{view.json,diff.patch,files.txt,.complete}`
  with the `.complete` sentinel **last**.
- The detached worker polls for `.complete` (≤ 2 s) and reads the cache if
  present; otherwise it falls through to its existing `gh` CLI path.

Constraints the pattern obeys:

- **Server reads context from inherited env, not from the JSON-RPC input.**
  `${tool_input.command}` is the only template field the harness substitutes
  reliably; everything else (`CLAUDE_SESSION_ID`, `GITHUB_PERSONAL_ACCESS_TOKEN`)
  is read server-side from `os.environ` at request time.
- **Sentinel-last write order** lets readers detect a complete cache without
  locking: the consumer waits on `.complete` and only reads the other files
  once it appears.
- **Graceful fallthrough** — when the MCP path fails for any reason
  (no token, network timeout, unsupported remote, MCP not connected), the
  server returns `{ok:false, reason:...}` and the consumer falls back to
  whatever it would have done absent the MCP. The MCP path is an
  optimization, never a dependency.
- **No subprocess to the legacy CLI from inside the MCP server.** The server
  uses `urllib.request` exclusively. Any `gh` invocation from the server
  would re-introduce the very subprocess overhead the cache exists to avoid.

## Pipeline Scratchpad Protocol

Agents share findings within a pipeline run via the scratchpad. See `rules/autonomous-intelligence.md` for full details.

### Reading (On Spawn)
The orchestrator injects scratchpad findings into the agent's prompt. Agents do not read the scratchpad directory directly — the orchestrator curates what's relevant.

### Writing (Before Completion)
Before completing, write discoveries to `pipeline-state/{task-id}/scratchpad/{role}-{phase}.md`. Use YAML frontmatter with `category: discovery|warning|pattern|fragility|decision`. Only write genuinely useful findings, not task narration. If nothing noteworthy was discovered, skip this step.

## Agent Memory Protocol

Agents accumulate per-project knowledge in `agent-memory/{role}/{project-hash}/memory.md`. This is institutional knowledge — what the agent has learned about a specific codebase across pipelines.

### Writing Memory
Before completing, if the agent learned something project-specific:
1. Check if `~/.claude/agent-memory/{role}/{project-hash}/memory.md` exists (create directory + file if not)
2. Append: `- {YYYY-MM-DD}: {one-line learning}`
3. Keep under 50 lines — prune oldest entries if file exceeds limit
4. Only write genuinely useful project knowledge, not task-specific notes

### What to Remember
- Project conventions not in CLAUDE.md (e.g., "this project uses barrel exports")
- Recurring patterns (e.g., "auth module has complex session lifecycle — read session.ts first")
- Known fragile areas (e.g., "payment webhook handler is timing-sensitive")
- Build/test quirks (e.g., "tests require DATABASE_URL set, not mocked")

### What NOT to Remember
- Task-specific details ("added login button to header")
- Information already in project CLAUDE.md
- Temporary state that won't apply next time

## Main-Branch Invariant

> **IRON LAW: REPO_ROOT HEAD STAYS ON `main` FOR THE ENTIRE DURATION OF EVERY PIPELINE RUN.**

Every git mutation that would move HEAD runs against a *worktree path*, expressed via an explicit delegation prefix in the command string. This is what allows multiple Claude Code sessions to coexist on the same physical clone without branch-state stomping.

### Forbidden bare forms (caught by `hooks/main-branch-guard.sh`)

- `git checkout <branch>` / `git checkout -b <branch>`
- `git switch <branch>` / `git switch -c <branch>`
- `git branch -d <name>` / `git branch -D <name>` where `<name>` is a protected branch (`main`/`master`), the currently checked-out branch, or run from outside a git repo (fail-closed)
- `git reset --hard ...`
- `git merge <ref>` (including bare `git merge --ff-only` with no explicit target)
- `git rebase <upstream>`
- `git pull <remote> <non-main-branch>` (explicit non-main branch)
- `git fetch <remote> <src>:<local-dst>` (refspec writing a local ref, e.g. `main:main`, `pull/123/head:pr-123`)
- `git push <remote> <src>:main` (writing remote main)
- `gh pr create ...`

### Allowed delegated forms

- `git -C <worktree-path> <cmd>`
- `git --git-dir=<worktree-path>/.git <cmd>`
- `cd <worktree-path> && <cmd>`
- `(cd <worktree-path> && <cmd>)`

`;`-separator does NOT count as delegation. `cd /tmp/x; git checkout foo` is **forbidden** — the `;` separator does not compose semantically with `cd` to guarantee the second clause runs in the new cwd. Only `&&` does. (Mechanically: `split_clauses` splits on `;` too, so a standalone `git checkout foo` clause is evaluated on its own and rejected as a bare form.) Use `&&` or the `git -C` / `git --git-dir=` flags.

### Always allowed (any cwd, any form)

Read-only ops (`git status|log|diff|show|rev-parse|describe|blame`), `git fetch <remote>` without refspec, `git fetch --all`, refspecs that write only `refs/remotes/...`, `git worktree {add,list,remove,prune}`, `git push <remote> <branch>` to non-main destinations, `git add|commit|tag|notes`, `git pull`, `git pull origin`, `git pull origin main`, `git pull [flags] origin main` (updating main is safe — fast-forward only, never moves HEAD to a different branch), `git branch -d|-D <non-current-non-protected-branch>` (deleting a branch that is not currently checked out and is not `main`/`master` does not move HEAD; fails-closed outside a git repo), `git merge --ff-only <main-equivalent>` where the explicit target is one of `origin/main`, `main`, `upstream/main`, `origin`, or `upstream` (bare `git merge --ff-only` with no target is forbidden — it merges FETCH_HEAD, which could be any previously-fetched ref).

### How agents must operate

- Agents always have a worktree assigned by the orchestrator. The path is in the spawn prompt.
- Mutate via `git -C "$WORKTREE" <cmd>` or `(cd "$WORKTREE" && <cmd>)`. Never type a bare HEAD-moving command.
- The `gh pr create` call runs INSIDE a `(cd "$WORKTREE" && ...)` wrapper. If you find yourself typing a bare `gh pr create`, stop — the guard will block it.

### Verification

At any observation point in any session:

```bash
git -C "$REPO_ROOT" rev-parse --abbrev-ref HEAD
```

must return `main`. The `main-branch-guard.sh` PreToolUse Bash hook prevents violations dynamically; the `worktree-cwd-check.sh` SubagentStop hook diagnoses any violation that slipped through (post-hoc forensics + drift detection).

### Why this matters

The harness-of-harness model lets the user spawn parallel sessions via `scripts/new-session.sh`, each in its own worktree under `$HOME/.claude-sessions/`. Those worktrees share state directories with REPO_ROOT (per `knowledge/session-isolation-patterns.md`). If REPO_ROOT HEAD moves, every concurrent session's git operations start fighting for the same branch — pull/fetch/merge become non-deterministic, eval baselines stamp against the wrong SHA, trajectory writers and observation-capture log against the wrong commit graph, and the human user sees "why is HEAD on `feature/foo`?!".

### Why command-shape inspection (not cwd inspection)

The guard inspects the COMMAND STRING the agent literally typed, not the cwd of the spawned Bash process. The harness reliably exposes `tool_input.command` (every existing Bash hook in the codebase reads it); it does NOT reliably expose `tool_input.cwd` for subagent calls (no existing hook in this codebase reads it). Command-shape is a single source of truth: agents either type a delegated form (allowed) or a bare form (forbidden), with no hidden state to chase. This makes the rule decidable from the command string alone, with no per-process cwd resolution.

Trade-off accepted: bare `git checkout foo` is forbidden universally — even from inside a worktree. Inside a worktree the agent must still write `git -C "$WORKTREE" checkout foo` (or `cd "$WORKTREE" && git checkout foo`). This is tighter than strictly necessary, and it is intentional: it makes the rule trivially auditable from the command string alone.

### Enforcement hooks

- `hooks/main-branch-guard.sh` — PreToolUse Bash hook. Inspects `tool_input.command`, blocks (exit 2) any forbidden bare form, logs to `metrics/$SESSION/main-branch-violations.jsonl` with `source: "prevented"`.
- `hooks/worktree-cwd-check.sh` — SubagentStop hook. Re-confirms prevented violations and detects drift (`git -C "$REPO_ROOT" rev-parse --abbrev-ref HEAD != "main"`), appending `source: "post-confirmed"` and `source: "drift-detected"` records. Diagnostic only — never blocks.

### Non-LLM Gates on Destructive Verbs

> **Iron law.** Destructive verbs do NOT clear on LLM judgement alone. They require a non-LLM, time-bounded human-set token before the harness will let them through.

The PocketOS Apr 27 2026 incident is the motivating case: an LLM-blessed deploy
script ran `volumeDelete` on a production volume that no human had reviewed in the
60 seconds before execution. The agent had been told the volume was a staging
artifact; the orchestrator had not been told it was attached to production. The
LLM correctly executed the literal instruction. There was no second gate.

The Non-LLM Gate fixes that class of failure for an enumerated set of verbs.
The list is the SOURCE OF TRUTH at `hooks/_lib/destructive-verbs.txt` — one ERE
pattern per line — and is loaded by `hooks/_lib/destructive-verb-detect.sh`.
`hooks/main-branch-guard.sh` invokes the destructive-verb module BEFORE its
HEAD-mutation check, so destructive verbs are caught even when they appear in
shell forms that would otherwise pass the main-branch invariant (e.g.
`(cd "$WT" && fly destroy my-app)` would have HEAD-discipline-clean delegation
prefixes but is still gated).

**The list (canonical — see `hooks/_lib/destructive-verbs.txt` for the live regex):**

| Verb / pattern | Class |
|---|---|
| `volumeDelete` | Cloud volume deletion |
| `aws s3 rb` | S3 bucket removal |
| `gcloud sql instances delete` | GCP SQL instance teardown |
| `railway down` | Railway service teardown |
| `fly destroy` | Fly.io app teardown |
| `DROP TABLE`, `TRUNCATE` | Schema/data destruction |
| `git push --force-with-lease` (and `-f` / `--force`) to `main`/`master`/`release`/`production`/`staging`/`develop` | Force push to non-feature branch |
| `rm -rf $HOME` / `rm -rf ~` | Filesystem destruction |
| `kubectl delete namespace prod` (or `production`) | Kubernetes prod teardown |

**Confirmation contract:**

To run any of the above, BOTH must hold within the last `CLAUDE_DESTRUCTIVE_CONFIRM_TTL`
seconds (default `600`):

1. `CLAUDE_DESTRUCTIVE_CONFIRM=I-have-a-restorable-backup-elsewhere`
2. `CLAUDE_DESTRUCTIVE_CONFIRM_TS=$(date +%s)`

Both env vars must be exported in the shell that invokes the destructive command.
The token is verbatim — case-sensitive, hyphenated, no quotes. The TS is unix
seconds. The orchestrator should NOT auto-set these vars; a human (or a tightly-scoped
deploy operator account with a documented backup) sets them.

When the gate fires WITHOUT a valid token, the hook logs a JSONL record at
`metrics/$SESSION/main-branch-violations.jsonl` with `source: "destructive-verb"`
and `action: "prevented"`, prints a block message naming the offending command,
and exits 2.

**Why time-bounded:** A static "yes I'm sure" token would persist in shell
history forever and become useless. A 600-second window forces a human to
re-export the token immediately before the destructive operation, which is the
cheapest possible non-LLM gate.

**Why a separate file:** the list grows with new cloud APIs and new failure
modes. Keeping the patterns in `hooks/_lib/destructive-verbs.txt` (one ERE per
line, `#` for comments) lets us add entries without editing executable code,
and lets the test in `tests/test_destructive_verb_block.py` and
`tests/shell/test_destructive_verb_block.bats` enumerate the file directly.

## Portable Config Dir (`CLAUDE_CONFIG_DIR`)

Every config-loading reference inside the harness MUST go through `${CLAUDE_CONFIG_DIR:-$HOME/.claude}`. Bare `~/.claude/` and bare `$HOME/.claude/` are FORBIDDEN in the following positions:

- `source` lines inside `hooks/*.sh` and `hooks/_lib/*.sh`
- `command:` strings in `settings.json` that invoke harness hook scripts (e.g., `bash …/hooks/X.sh`)
- `args:` paths in `settings.json` `mcpServers` entries that point at server scripts shipped with the harness
- `command:` strings in `settings.json` `statusLine` that point at harness scripts

Why: `$HOME` and the harness config dir are not always the same path. Web-sandbox sessions (Claude Code on the web), corporate-managed homedirs, NFS-mounted homes, and any container with a non-default `$HOME` all break the assumption that `~/.claude` is the source tree. Claude Code documents `CLAUDE_CONFIG_DIR` as the supported env var for relocating the config tree, but shell `~` expansion is `$HOME`-driven and ignores `CLAUDE_CONFIG_DIR`. The only reliable form is the parameter-expansion default: `"${CLAUDE_CONFIG_DIR:-$HOME/.claude}/…"`. Always quote — paths may contain spaces.

Example — config-loading source line in a hook:

```bash
# Wrong (breaks if HOME ≠ config dir)
source ~/.claude/hooks/_lib/log.sh
source "$HOME/.claude/hooks/_lib/log.sh"

# Right (portable)
source "${CLAUDE_CONFIG_DIR:-$HOME/.claude}/hooks/_lib/log.sh"
```

Example — hook command in settings.json:

```json
{
  "type": "command",
  "command": "bash \"${CLAUDE_CONFIG_DIR:-$HOME/.claude}/hooks/main-branch-guard.sh\""
}
```

Out of scope (NOT covered by this convention):

- **Runtime data paths** (`$HOME/.claude/metrics/`, `$HOME/.claude/learning/`, `$HOME/.claude/pipeline-state/`, etc.) — these stay rooted at `$HOME/.claude/` for now. A future `CLAUDE_DATA_DIR` env var may relocate them; that is a separate concern from config loading.
- **Permissions globs in `settings.json`** (`Write($HOME/.claude/**)`, etc.) — these gate where Claude Code may write at runtime; they remain `$HOME/.claude` because the runtime data dir convention has not yet split from `$HOME`.

Enforced by `tests/test_portable_config_dir.py` — drift in either position fails CI.

## Shell Environment

Agent shells may not inherit the user's version manager (nvm, rbenv, pyenv, rustup, etc.).

Before running build/test commands, agents MUST:
1. Check if the command exists: `which npm` / `which bundle` / `which python` (or equivalent)
2. If not found, source the user's shell profile: `source ~/.zshrc 2>/dev/null || source ~/.bashrc 2>/dev/null`
3. If still not found, report the error — do not retry blindly

The project CLAUDE.md's Commands section is the source of truth for how to run tests.
If commands fail with "command not found", check the project CLAUDE.md first.

## Internal Eval Gate (harness changes)

PRs that modify ANY of the following directories MUST run `/harness:internal-eval run` and produce zero regressions before merge:
- `rules/`
- `hooks/`
- `skills/`
- `agents/`

The agent opening the PR is responsible for invoking `/harness:internal-eval run`. The verdict must be `EVAL_PASSED` (zero regressions on deterministic cases). `EVAL_FAILED` blocks merge.

`eval/` changes themselves do NOT trigger this gate (would be circular).

Exceptions:
- Docs-only changes to `.md` files outside of SKILL.md / agent definitions: gate may be skipped with an explicit note in the PR body.
- Emergency fixes with incident ticket reference: gate may be deferred with explicit post-merge commitment to re-run.

## Fresh Verification Requirement

> **IRON LAW: NO COMPLETION CLAIMS WITHOUT FRESH VERIFICATION EVIDENCE.**

Before any agent signals completion (BUILD_COMPLETE, VERIFIED, etc.):
1. Run the full test suite NOW — not "tests passed earlier"
2. Run the type checker NOW — not "tsc passed when I last ran it"
3. Stale output from earlier in the session is NOT evidence
4. If you cannot run verification commands, report this — do not claim completion

"I ran the tests 50 turns ago" is not verification. Run them again.

## Dependency Management (agent side)

If your task needs new packages, install them in your worktree as part of implementation work:
- Run the package manager command (`npm install`, `bundle add`, `pip install`, etc.)
- Verify the install (`npm ls <pkg>`, `bundle info <pkg>`)
- Commit `package.json`/`Gemfile` and lock file separately with a chore commit

The orchestrator never installs dependencies — that's always the build agent's job. The orchestrator-side rationale and `Why this matters` rules live in `~/.claude/orchestrator/agent-orchestration.md` § Dependency Management.

## Resource Bounds

The harness caps subagent recursion depth and per-job wall-clock time so no
pipeline can run away. Caps live in the `settings.json` `env` block (single
source of truth):

| Bound | Default | Env override |
|-------|---------|--------------|
| Subagent recursion depth | 3 | `CLAUDE_SUBAGENT_MAX_DEPTH` |
| Subagent wall-clock | 1800s | `CLAUDE_SUBAGENT_MAX_RUNTIME` |
| Teammate wall-clock | 3600s | `CLAUDE_TEAMMATE_MAX_RUNTIME` |

**Enforcement hooks:**

- `hooks/depth-guard.sh` (PreToolUse Agent): refuses spawn when
  `CLAUDE_SUBAGENT_DEPTH >= max`. Top-level orchestrator (variable unset)
  is treated as depth 0. Logs `metrics/$SID/depth-violations.jsonl` with
  `record_type:"depth_violation"`, `depth`, `max_depth`, `subagent_type`,
  `task_id`, `action:"prevented"`. Exit 2 on block.
- `hooks/runtime-guard.sh` (PreToolUse Agent|Bash|Write|Edit; Read
  excluded — high-volume, fast-bounded). **Owns wall-clock cap
  ENFORCEMENT only** — historical per-call durations are captured
  separately by `hooks/tool-timing-capture.sh`. Mode A on Agent records
  `metrics/$SID/subagent-runtimes/<key>.start` (idempotent — first-seen
  timestamp wins; the start-file is the in-flight probe Mode B requires
  because the post-completion `tool-timings.jsonl` stream cannot detect
  an agent stuck mid-call). Mode B on Bash|Write|Edit performs an
  orchestrator-level global scan and emits a shutdown directive on
  stderr (exit 2) for any start-file whose elapsed time exceeds the
  per-class cap. No `CLAUDE_SUBAGENT_ID` dependency — Option C global
  scan reads start-file bodies (`<unix_ts>:<class>:<display>`) for
  stderr enrichment. Logs `metrics/$SID/runtime-violations.jsonl`.
- `hooks/tool-timing-capture.sh` (PostToolUse + PostToolUseFailure) —
  appends one compact JSON line per completed tool call to
  `metrics/$SID/tool-timings.jsonl` with fields `ts`, `tool`,
  `duration_ms`, `success`, `agent_role`, `task_id` (last two omitted
  when absent). Reads `duration_ms` from the Claude Code 2.1.119+
  payload; `success` is `true` for PostToolUse and `false` for
  PostToolUseFailure. JSON emission goes through `python3 json.dumps`
  via `hooks/_lib/tool-timing-emit.py` — never bash `printf` for
  dynamic values (load-bearing learned instinct). This is the
  canonical historical-duration source for any consumer that needs
  completed-call timing without re-deriving from start-files.
- `hooks/subagent-stop-trajectory.sh` — owns cleanup of the matching
  `<key>.start` file on SubagentStop, preventing stale-timestamp false
  positives on re-spawn with the same key. Shared SHA1 derivation via
  `_lib/runtime-guard-key.sh`.

**Shutdown semantics by class** (honest Path-B disclosure):

- **Teammate** (`team_name` non-empty): stderr block is the exact
  `SendMessage({type:"shutdown_request", name:"<display>"})` form,
  directly actionable per `## Teammate Lifecycle (team phases)` above.
- **Non-team subagent**: stderr says "next tool call blocked; orchestrator
  should re-dispatch per rules/operational-protocol.md". An equivalent
  out-of-band kill is not currently exposed by the Agent tool input schema; the
  next tool the runaway subagent attempts is refused at PreToolUse, the
  orchestrator interprets the violation log, and decides re-dispatch
  (retry-twice-then-escalate). Mirrors the `pre-agent-thinking.sh` Path-B
  precedent — a degraded-but-correct enforcement today, one-line flip
  when the API surface lands.

**Depth propagation contract:** orchestrators MUST set
`CLAUDE_SUBAGENT_DEPTH = parent_depth + 1` in the shell that invokes Agent
before each spawn. The child inherits the variable via process env. See
`orchestrator/agent-orchestration.md > § Spawn Procedure` and
`orchestrator/parallel-dispatch-details.md > § Team Dispatch` for the
literal example bash assignment.

**Forensics:** `metrics/$SID/depth-violations.jsonl` and
`metrics/$SID/runtime-violations.jsonl` join on `session_id` + `task_id`
for retroactive auditing of cap breaches.

## Per-Agent Tool Scoping

Every agent's `tools:` frontmatter is the declared allowlist of tools that
agent may invoke. The list is a YAML sequence (one tool per line) and is
the single source of truth — no other file restates per-agent tool grants.
The current spec for the seven F1-touched roles lives in
`tests/test_agent_tools_spec.py` as a snapshot; any drift in either
direction (frontmatter or spec) fails CI.

**Enforcement (Path-B, currently log-only):**

- `hooks/pre-agent-allowlist.sh` (PreToolUse Agent, position 5 — after
  `pre-agent-thinking.sh` and `pre-agent-advisor.sh`, before
  `depth-guard.sh`). Reads the spawned `subagent_type`, loads the
  matching `agents/<role>.md` frontmatter via
  `hooks/_lib/agent_tools_loader.py`, and computes a subset check against
  `tool_input.allowed_tools`.
- Resolver (`hooks/_lib/tool_allowlist_resolver.py`) returns one of:
  - `skip` — non-Agent tool, or `subagent_type` fails the kebab-case
    safety regex (`agent_path_validator`).
  - `advisory` — frontmatter declares no tools, OR `tool_input` does not
    expose `allowed_tools` (current schema state).
  - `ok` — every requested tool is present in the frontmatter list.
  - `would_block` — at least one requested tool is NOT in the frontmatter
    list. Logged with the offending tool names. **No spawn is refused
    today** — the field is not yet exposed by the Agent input schema.
- Logged to `metrics/$SID/tool-allowlist.jsonl` with
  `source: "path-b-advisory"`. Each line is capped at 1024 bytes;
  `agent_role` is capped at 64 bytes; `CLAUDE_SESSION_ID` is sanitized
  against directory traversal before metrics path resolution.
- Disable per-session with `CLAUDE_DISABLE_TOOL_ALLOWLIST=1`. Suppressed
  by `CLAUDE_HOOK_PROFILE=minimal` (matches the
  `check_hook_profile "standard"` gating used by adjacent advisory hooks).

**Promotion to enforcement** is a one-line flip in
`hooks/pre-agent-allowlist.sh` (exit 2 on `would_block`, mirroring the
`pre-agent-thinking.sh` precedent) the moment Claude Code exposes
`allowed_tools` on Agent spawn payloads. The resolver and tests are
already enforcement-ready.

**For dynamic agents:** the same contract applies. The Dynamic Agent
Template in `orchestrator/agent-orchestration.md` MUST declare `tools:`
as a YAML list — comma-separated strings break the loader. If a dynamic
agent's `tools:` list is missing entirely, the resolver returns
`advisory` (no enforcement), so frontmatter omissions become silent —
always declare the list.

## Reversibility Escapes (PreToolUse Agent hooks)

Run-time toggles to short-circuit a specific gate to `exit 0` without editing the hook file or `settings.json`. Use when an enforcement flip mis-classifies a legitimate spawn; investigate, then unset.

| Env var | Hook | Effect when set to `1` |
|---|---|---|
| `CLAUDE_DISABLE_TOOL_ALLOWLIST` | `pre-agent-allowlist.sh` | Skip allowlist subset check; no JSONL line; hook exits 0. |
| `CLAUDE_DISABLE_THINKING_GATE` | `pre-agent-thinking.sh` | Skip thinking-defaults resolver; no `hook-injections.jsonl` line; hook exits 0. |
| `CLAUDE_DISABLE_ADVISOR_GATE` | `pre-agent-advisor.sh` | Skip advisor-pairing resolver; no `advisor-dispatch.jsonl` line; hook exits 0. |
| `CLAUDE_DISABLE_INSTINCT_INJECTION` | `instinct-injector.sh` | Skip instinct resolution; no JSONL line; hook exits 0. |
