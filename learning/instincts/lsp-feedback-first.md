---
id: lsp-feedback-first
confidence: 0.6
roles:
  - software-engineer
  - frontend-engineer
domain: build
---

## Pattern

Before each Edit on a typed file, query the appropriate `mcp_lsp_diagnostics_*` tool on the current path. If errors exist, address them before adding new code.

## Why

Editing typed code without first reading the LSP's view of the file produces compounding errors: type drift, missing imports, broken references that the agent only discovers at the next test run. Querying diagnostics first surfaces existing problems and locks in current invariants before adding more.

## How to Apply

1. Identify the file's language (`.ts`, `.tsx`, `.js`, `.jsx` → use `mcp_lsp_diagnostics_ts`; `.py` → use `mcp_lsp_diagnostics_py`).
2. Call the tool with `{"path": "<file>"}` and read the diagnostics.
3. If errors exist:
   - Read them in full (severity, range, message).
   - Decide whether they overlap your edit zone. If so, fix them first or scope your edit to avoid the broken region.
   - Never add new code that depends on a currently-broken declaration without acknowledging the dependency in your plan.
4. After your edit, re-query diagnostics to confirm no new errors were introduced.

## When NOT to Apply

- Untyped files (plain Markdown, JSON without schema, shell scripts) — the LSP has nothing to say.
- Files outside the project's TypeScript / Python config roots (the LSP cannot resolve them).
- Pure deletion edits that remove a broken declaration (the diagnostic will resolve naturally).

## Source

`learning/instincts/lsp-feedback-first.md` — initial confidence 0.6 based on prior-art consensus that LSP-first editing is a strong instinct in IDE-driven development. Will be refined as observation data accrues.
