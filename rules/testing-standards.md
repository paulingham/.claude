# Testing Standards

## TDD: Red-Green-Refactor (MANDATORY)
1. **RED**: Failing test first. Verify it fails for the right reason.
2. **GREEN**: Minimum code to pass.
3. **REFACTOR**: Clean up while green.

Never skip RED — if you didn't see it fail, you don't know the test works.

## Pyramid
- **70% Unit** — isolated, mocked deps, milliseconds
- **20% Integration** — real DB, service boundaries, seconds
- **10% E2E** — critical user workflows only

## Gates
- 80% coverage on critical paths
- No `xit`, `pending`, or `skip` — delete untestable specs

## Zero Noise
- Every output line is a test result or a real error
- No warnings, deprecations, leaked test data, or pending specs
- Redirect test IO to StringIO, not real stderr/stdout

## Proof of Correctness (Beyond Tests)

Tests passing is necessary but not sufficient. For every feature:
- **Tier 1**: Contract tests against real boundaries (not mocks for critical paths)
- **Tier 2**: Smoke tests that exercise the actual feature end-to-end
- **Tier 3**: Targeted mutation testing on changed files (verify tests catch real bugs)

Feature is VERIFIED when all three tiers pass. No tier is optional.

## Known Deprecations (append-only)
- `:unprocessable_entity` → `:unprocessable_content` (Rack 3.x, HTTP 422)
