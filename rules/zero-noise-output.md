# Zero Noise Output Rules

## Principle
Every line of test/build/CI output is either a test result or a real error. No warnings, no deprecations, no leaked test data, no pending specs.

## Test Output
- NEVER use `xit`, `pending`, or `skip`. Delete untestable specs and file a ticket if needed.
- NEVER write test data to real `$stderr`/`$stdout`. Redirect to StringIO in specs that spawn processes or use IO pipes.
- ALWAYS use forward-compatible Rack status symbols (`:unprocessable_content` not `:unprocessable_entity`).

## Deprecation Response
When a deprecation warning appears:
1. Fix it immediately — do not ship known deprecations.
2. Fix ALL occurrences project-wide, not just the one you touched.
3. Append the pattern to this file so agents never re-introduce it.

## Known Deprecations (Fixed)
- `:unprocessable_entity` → `:unprocessable_content` (Rack 3.x, HTTP 422)
