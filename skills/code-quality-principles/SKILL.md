---
name: "Code Quality Principles"
description: "SOLID, DRY, TDD red-green-refactor, service object patterns, dependency injection. Use when implementing features to ensure clean, maintainable, testable code that follows engineering standards."
---

# Code Quality Principles

## What This Skill Does

Enforces code quality principles for any project:
1. **Testing Pyramid (70/20/10)** - Unit, Integration, E2E distribution
2. SOLID principles applied in context
3. DRY (Don't Repeat Yourself) patterns
4. TDD red-green-refactor cycle
5. Service object patterns
6. Dependency injection for testability

---

## Testing Pyramid (70/20/10)

### Target Distribution
```
+------------------------------------------+
|           E2E Tests (10%)                |  Critical user journeys only
|       Persona-based, expensive           |
+------------------------------------------+
|       Integration Tests (20%)            |  Request specs, API tests
|    Component interactions, API flows     |
+------------------------------------------+
|          Unit Tests (70%)                |  Model, Service, Job specs
|   Fast, isolated, comprehensive          |
+------------------------------------------+
```

### Unit Tests (70%) - ALWAYS FIRST

Every new feature MUST have:
- **Model attribute tests** (validation, default values, associations)
- **Service method behavior tests** (happy path, error cases)
- **Job execution tests** (enqueue, perform, retry)
- **Policy/ability tests** (authorization)

### Integration Tests (20%)

Every new feature MUST have:
- **Request specs** for controller actions
- **API contract tests** for external integrations
- **Background job integration tests**
- **Service integration tests** (multi-service coordination)

### E2E Tests (10%) - Persona-Based

Every user-facing feature MUST have:
- At least ONE persona journey test
- Both happy path AND error path coverage

---

## Elephant Carpaccio (Delivery Approach)

Implement features in the **thinnest possible vertical slices**.

### Core Principles

1. **Vertical Slices** - Each slice delivers end-to-end functionality
   - DON'T: Build all DB then all API then all UI (horizontal layers)
   - DO: Build one feature complete (DB + API + UI + tests)

2. **Thin Slices** - Make slices as small as possible
   - Each slice MUST be deployable independently
   - Each slice MUST be testable independently

3. **Working Software** - Every slice produces working software
   - No "90% done" - either it works or it doesn't
   - Demo-able after each slice

---

## SOLID Principles

### S - Single Responsibility Principle

A class should have one reason to change. Keep controllers thin; extract business logic to service objects.

### O - Open/Closed Principle

Open for extension, closed for modification. Use Strategy pattern for swappable algorithms instead of adding case/when branches.

### L - Liskov Substitution Principle

Subtypes must be substitutable for their base types. Subclasses must honor parent contracts with the same return types.

### I - Interface Segregation Principle

Clients should not depend on interfaces they do not use. Split fat interfaces into focused, smaller ones.

### D - Dependency Inversion Principle

Depend on abstractions, not concretions. Inject dependencies via constructor to enable testing with fakes.

---

## DRY (Don't Repeat Yourself)

### When to Extract

**Rule:** Extract when you have 3+ similar instances (Rule of Three).

### When NOT to Extract

**Don't extract for 1-2 instances** -- premature abstraction adds complexity without benefit.

---

## TDD Red-Green-Refactor

### The Cycle

```
RED -> GREEN -> REFACTOR -> RED -> ...
```

1. **Red**: Write a failing test that defines expected behavior
2. **Green**: Write minimum code to make the test pass
3. **Refactor**: Improve design while keeping tests green
4. **Repeat**: Add the next test

---

## Service Object Pattern

### When to Use
- Complex business logic
- Multi-model coordination
- External API integration
- Background job processing

### Pattern
```
ClassName.new(dependencies).call(args) -> Result
```

- Constructor receives dependencies (DIP)
- `.call` orchestrates private methods
- Single public entry point per class
- All other methods are private

---

## Code Review Checklist

### SOLID Violations
- [ ] Classes with multiple responsibilities
- [ ] Hard-coded dependencies
- [ ] Subclasses breaking parent contracts
- [ ] Fat interfaces clients don't fully use
- [ ] Dependencies on concretions, not abstractions

### DRY Violations
- [ ] Duplicated logic (3+ instances)
- [ ] Copy-pasted code blocks
- [ ] Similar conditional structures

### TDD Quality
- [ ] Tests written first (not after)
- [ ] Tests test behavior, not implementation
- [ ] Test coverage >= 80% per file
- [ ] Edge cases covered
- [ ] Failures tested

### Security
- [ ] No SQL injection
- [ ] No XSS vulnerabilities
- [ ] Mass assignment protected
- [ ] Authentication/authorization checked

---

## Anti-Patterns to Avoid

### God Objects
One class doing everything -- split into focused service objects.

### Premature Abstraction
Wait for the Rule of Three before extracting shared abstractions.

### Testing Implementation
Test behavior (outcomes), not private methods or internal calls.
