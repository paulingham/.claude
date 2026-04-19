---
category: fragility
---
Allowlist file-glob matcher semantics: patterns containing `/` require full-path matching with leading `*/` wildcard — basename/endswith checks miss them. Covered by test_allowlist_matcher tests after fix.

---
category: warning
---
`allowlist_loader._safe_parse` must catch broad `Exception`, not a whitelist of (JSONDecodeError, OSError). UnicodeDecodeError on non-UTF8 user files is a ValueError, not OSError, and would crash the capture subprocess. AC7 fail-safe posture requires the empty allowlist fallback on ANY parse failure.

---
category: discovery
---
L1 "unrelated settings.json on S6 branch" was a false positive from code-reviewer diffing against an out-of-date main. `git log main..HEAD -- settings.json` returned empty — no S6 commit touched settings.json. Main had moved forward (b7ae469 path-scoped allows) while S6 branched earlier. No revert needed.
