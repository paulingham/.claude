#!/usr/bin/env bash
# Portable SHA-256 + repo-hash + plan-cache-key helpers (agentic plan cache).
# Source this file; call _repo_hash or _plan_cache_key.
# Design (HIGH-eng-1, plan.md Citation #11): `git ls-tree --name-only -r HEAD <dirs>`
# is leaf-content-blind by design — content edits do NOT change the path-set
# enumeration; file add/rename/delete DO. CLAUDE.md content is folded in
# separately so doc edits invalidate the cache.

_sha256_hash() {
  command -v sha256sum >/dev/null 2>&1 && { sha256sum | awk '{print $1}'; return; }
  shasum -a 256 | awk '{print $1}'
}

_repo_hash_stable_dirs() {
  local cfg=".claude/plan-cache.json"
  [[ -r "$cfg" ]] && command -v jq >/dev/null 2>&1 || { echo "src/ lib/ app/"; return; }
  jq -r '.stable_dirs // ["src/","lib/","app/"] | join(" ")' "$cfg" 2>/dev/null \
    || echo "src/ lib/ app/"
}

_repo_hash() {
  local dirs claude_content tree
  read -r -a dirs <<<"$(_repo_hash_stable_dirs)"
  tree=$(git ls-tree --name-only -r HEAD -- "${dirs[@]}" 2>/dev/null)
  claude_content=$(cat CLAUDE.md 2>/dev/null || true)
  printf '%s\n--CLAUDE.md--\n%s' "$tree" "$claude_content" | _sha256_hash
}

_plan_cache_key() {
  command -v jq >/dev/null 2>&1 || return 1
  jq -cn --arg tc "$1" --arg rh "$2" --arg tr "$3" --arg cr "$4" \
    '{critical:$cr, repo_hash:$rh, task_class:$tc, tier:$tr}' | _sha256_hash
}
