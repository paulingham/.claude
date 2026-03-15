# Efficiency Rules

## DRY: Don't Repeat Yourself (MANDATORY)

- First occurrence: write the code
- Second occurrence: note the duplication
- Third occurrence: MUST refactor into a shared abstraction

## Class Design

- Single public entry point per class (`.call`, `.run`, `.execute`)
- All other methods are private implementation details
- If a class needs "and" in its description, split it

## Complexity Limits

- Method length: 5 lines max
- Cyclomatic complexity: 5 max
- Nesting depth: 2 max
- Class length: 50 lines max
