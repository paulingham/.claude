# Multi-Repo Protocol

> This protocol applies to projects that are already multi-repo. New projects default to modular monolith per `protocols/module-boundaries-protocol.md`. Adopt this protocol only when a forcing function is named and the pipeline has routed to `/service-extraction` or `/microservices-scaffold`.

## Project Manifest

The manifest is the single source of truth for multi-repo projects. It tracks repos, their relationships, service config, and deployment order.

### Location

- `~/.claude/manifests/{project-name}.md` — orchestrator-managed
- Auto-created by the pipeline when multi-repo work is detected
- Never manually created by the user — the pipeline handles it

### Format

```markdown
---
name: {project-name}
created: {ISO 8601}
updated: {ISO 8601}
---

## Repos
| Name | Path | Role | GitHub | Status |
|------|------|------|--------|--------|
| {name} | {local path} | {provider/consumer/standalone} | {org/repo} | {active/planned/archived} |

## Dependencies
| Consumer | Provider | Contract | Type |
|----------|----------|----------|------|
| {consumer-repo} | {provider-repo} | {path to contract file} | {openapi/protobuf/event-schema} |

## Deploy Order
1. {repo-name} (no deps)
2. {repo-name} (after: {dep})

## Services
### GitHub
- org: {github org}
- visibility: {private/public}
- template: {org/template-repo or "none"}
- branch_protection: {true/false}
- required_reviews: {N}
- environments: [{staging, production}]

### Deploy
| Repo | Platform | App Name |
|------|----------|----------|
| {repo} | {fly.io/vercel/heroku/docker} | {app-name} |
```

### Auto-Creation Triggers

The pipeline creates a manifest automatically when ANY of these are true:
- Intake classifies work as service-extraction
- Intake classifies work as cross-repo feature
- A project CLAUDE.md has `## Service Context` with upstream/downstream entries
- The user's request references multiple repos or "separate service"
- The scaffold phase needs to create a new GitHub repo

When auto-creating:
1. Read current repo's GitHub remote: `gh repo view --json owner,name`
2. Read `## Service Context` from project CLAUDE.md if it exists
3. Create manifest with current repo as first entry
4. Add planned repos from the architect's output
5. Populate GitHub config from current repo's org settings

### Manifest Updates

The pipeline updates the manifest as work proceeds:
- New repo created → add to Repos table, set status to "active"
- Contract generated → add to Dependencies table
- Deploy target configured → add to Deploy section
- Repo archived/removed → set status to "archived"

## Multi-Repo Pipeline State

### Detection (Automatic — Part of Pipeline Pre-flight)

During pipeline pre-flight (Step 2 of `/harness:pipeline`), detect multi-repo needs:

1. Check `~/.claude/manifests/` for a manifest matching the current project
2. If manifest exists → multi-repo mode
3. If no manifest but signals detected (see Auto-Creation Triggers) → create manifest, enter multi-repo mode
4. If no manifest and no signals → single-repo mode (existing behavior, no change)

### State File Extension

Multi-repo pipelines add a `repos` section to the pipeline state file:

```markdown
---
task_id: {id}
phase: {phase}
verdict: {verdict}
timestamp: {ISO 8601}
scale: {scale}
manifest: {manifest path}
---

## Repos
| Repo | Branch | Phase | Verdict |
|------|--------|-------|---------|
| {repo-1} | {branch} | {build/review/etc} | {verdict} |
| {repo-2} | {branch} | {build/review/etc} | {verdict} |

## PR Manifest
| Repo | Branch | PR | Depends On | Status |
|------|--------|-----|------------|--------|
| {repo} | {branch} | #{N} | {dep or "—"} | {open/approved/merged} |

## Merge Order
1. {repo}#{N} (no deps)
2. {repo}#{N} (after: {repo}#{N})
```

Per-repo phase files sit alongside: `{task-id}-{repo-name}-{phase}.md`

## Cross-Repo Agent Dispatch

### Repo-Aware Spawning

When spawning agents for multi-repo work, the orchestrator:

1. Reads the manifest to resolve repo paths
2. Includes `Working directory: {absolute-path}` in every agent prompt
3. Each agent works in ONE repo — never across repos in a single agent
4. Worktree isolation happens per-repo (each agent gets a worktree in its target repo)

### Parallel Build Across Repos

For independent repos (no build-time dependency):
- Spawn agents in parallel, one per repo
- Each agent uses `isolation: "worktree"` in their target repo
- Orchestrator merges all branches after all agents complete

For dependent repos (provider must build first):
- Build provider repo first
- After provider build complete → build consumer repos in parallel
- Follow the dependency graph from the manifest

## GitHub Repo Creation (Automated)

When the pipeline needs a new repo (service extraction, new service scaffold):

### Procedure
```
1. Read GitHub config from manifest (org, template, visibility)
2. gh repo create {org}/{name} --private [--template {template}]
3. gh api repos/{org}/{name}/branches/main/protection (if branch_protection: true)
4. Clone to local path (sibling of current repo, or path from plan)
5. Update manifest: add repo entry with status "active"
6. Run /harness:project-setup in new repo (auto — not a manual command)
7. Commit initial scaffold in new repo
```

### Defaults (When Config Not Specified)
- Org: from current repo's GitHub remote
- Visibility: private
- Template: none
- Branch protection: true, 1 required review
- Environments: staging + production

### No Manual Commands
GitHub repo creation is part of the scaffold phase. The pipeline:
1. Detects "new repo needed" from the architect's plan
2. Creates the repo automatically using the config
3. Scaffolds it with `/harness:infra-scaffold` + `/harness:project-setup`
4. Registers it in the manifest
5. Continues with the build phase

The user never runs a separate command. If the pipeline needs a repo, it creates one.

## Multi-PR Coordination

### Linked PRs

When shipping multi-repo work, `/harness:pr-creation` creates PRs in dependency order:

1. Read the manifest's dependency graph
2. Create PRs bottom-up (providers first, consumers last)
3. Each PR body includes cross-references:
   ```
   ## Related PRs
   - Depends on: org/provider-repo#12 (must merge first)
   - Depended on by: org/consumer-repo#8
   ```
4. Track all PRs in the pipeline state's PR Manifest section

### Merge Order Enforcement

The orchestrator merges PRs in topological order of the dependency graph:

1. Merge provider PRs first (no dependencies)
2. Wait for CI to pass on merged provider
3. Merge consumer PRs (dependencies satisfied)
4. If any merge fails → halt, report, don't merge remaining

### PR Labels (From Manifest Config)

If the manifest defines labels, apply them:
- `pipeline:build`, `pipeline:review`, etc. for phase tracking
- `cross-repo` for PRs that are part of a multi-repo change
- Custom labels from manifest config

## Deployment Ordering

### Dependency-Aware Deploy

Read the manifest's Deploy Order section:

1. Deploy providers first (no dependencies)
2. Health-check each provider after deploy
3. Only after provider is healthy → deploy consumers
4. Health-check consumers after deploy
5. Run cross-service smoke tests after all deployed

### Rollback Order

Reverse of deploy order:
1. Roll back consumers first
2. Then roll back providers
3. Verify health at each step

### Cross-Service Verification

After all services deployed:
1. Run contract tests between all connected services
2. Run end-to-end smoke tests
3. Monitor error rates for 5 minutes
4. If any failure → rollback in reverse order

## Integration with Existing Skills

| Skill | Multi-Repo Change |
|-------|-------------------|
| `/harness:intake` | Classifies multi-repo signals, triggers manifest creation |
| `/harness:pipeline` | Reads manifest, dispatches per-repo, tracks multi-repo state |
| `/harness:project-setup` | Registers repo in manifest, populates Service Context |
| `/service-extraction` | Creates repo via manifest config, updates manifest |
| `/cross-service-pipeline` | Reads manifest for repo paths, runs concrete contract tests |
| `/harness:pr-creation` | Creates linked PRs, enforces merge order |
| `/harness:deploy` | Deploys in dependency order, cross-service verification |
| `/microservices-scaffold` | Creates repo via manifest config |

All integrations are automatic. No skill requires manual invocation for multi-repo support.
