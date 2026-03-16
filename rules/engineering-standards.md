# Engineering Standards

## Code Shape
- Methods: 5 lines max, CC ≤ 5, nesting ≤ 2
- Classes: 50 lines max, single public entry point (`.call`/`.run`/`.execute`)
- DRY: 1st write it, 2nd note it, 3rd extract it

## Naming
- Intention-revealing, no abbreviations, describe what not how
- Booleans read as questions (`valid?`, `enabled?`, `is_active`)
- If a name needs a comment, rename it

## SOLID (one-liner reminders)
- SRP: one reason to change — OCP: extend, don't modify — LSP: honor contracts
- ISP: small interfaces — DIP: inject dependencies via constructor

## Error Handling
- Never fail silently — surface with context (correlation ID, input params, stack)
- Retry transient failures with exponential backoff
- Guard clauses on public methods

## Self-Sufficiency
- Validate your own work before marking done
- Run linting and tests before declaring complete
