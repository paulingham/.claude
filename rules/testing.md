# Testing Rules

## TDD: Red-Green-Refactor (MANDATORY)

1. **RED**: Write a failing test first. Verify it fails for the right reason.
2. **GREEN**: Write minimum code to pass. Not perfect, just working.
3. **REFACTOR**: Clean up while keeping tests green.

Never skip RED — if you didn't see it fail, you don't know the test works.

## Testing Pyramid

- **70% Unit** — isolated classes/methods, mock dependencies, milliseconds
- **20% Integration** — real database, service boundaries, seconds
- **10% E2E** — critical user workflows only, expensive

## Coverage

- Minimum 80% on critical paths
- One assertion per test when possible
- No `xit`, `pending`, or `skip` — delete untestable specs
