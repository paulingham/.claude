---
name: Testing Patterns
description: Test pyramid ratios, factory vs fixture, test doubles, contract testing, mutation testing, async patterns, and database cleaner strategies
type: reference
---

# Testing Patterns

## Test Pyramid

```
         /\
        /E2E\      10% — critical user journeys only (slow, brittle)
       /------\
      /Integr. \   20% — service boundaries, real DB (moderate speed)
     /----------\
    /    Unit    \  70% — isolated, mocked deps (milliseconds)
   /--------------\
```

- **Unit**: Pure functions, service objects, domain logic. Mock all I/O.
- **Integration**: Real database, real queue, real filesystem. Mock external APIs.
- **E2E**: Real browser/device, real stack. Critical journeys only.

Target: 80% coverage on critical paths. 100% on auth/payment/data integrity paths.

## Factory vs Fixture

### Factories (preferred)
```ruby
# FactoryBot (Ruby)
FactoryBot.define do
  factory :user do
    sequence(:email) { |n| "user#{n}@example.com" }
    name { "Test User" }
    role { :member }

    trait :admin do
      role { :admin }
    end

    trait :with_subscription do
      after(:create) { |user| create(:subscription, user: user) }
    end
  end
end

# Usage
user = create(:user, :admin)
user_with_sub = create(:user, :with_subscription)
```

```typescript
// factory-bot style for JS (rosie, fishery)
const userFactory = Factory.define<User>('user', () => ({
  id: sequence(),
  email: `user${sequence()}@example.com`,
  name: 'Test User',
  role: 'member',
}));
```

**Why factories over fixtures:**
- Factories create minimal required data — no hidden coupling
- Fixtures are global state — changes break unrelated tests
- Factories make test intent clear (you see what data matters)

## Test Data Builder Pattern

For complex object graphs:
```typescript
class UserBuilder {
  private attrs: Partial<User> = {};

  withEmail(email: string) { this.attrs.email = email; return this; }
  withRole(role: string) { this.attrs.role = role; return this; }
  asAdmin() { this.attrs.role = 'admin'; return this; }

  build(): User {
    return { id: 1, email: 'default@test.com', role: 'member', ...this.attrs };
  }
}

// Usage
const admin = new UserBuilder().asAdmin().withEmail('boss@co.com').build();
```

## Test Doubles

| Type | Definition | Use When |
|------|-----------|----------|
| **Stub** | Returns preset values, no verification | Controlling indirect inputs |
| **Mock** | Verifies calls were made (expectations set upfront) | Verifying indirect outputs |
| **Spy** | Records calls, verified after the fact | When you don't know upfront what to verify |
| **Fake** | Working implementation (e.g., in-memory DB) | Need realistic behavior without real infra |
| **Dummy** | Placeholder that's never used | Satisfying parameter requirements |

```typescript
// Stub — controls what the dependency returns
const emailService = { send: jest.fn().mockResolvedValue({ sent: true }) };

// Mock — verifies calls (set expectations before)
const emailService = { send: jest.fn() };
// ... run code ...
expect(emailService.send).toHaveBeenCalledWith({ to: 'user@test.com', subject: 'Welcome' });

// Fake — in-memory implementation
class InMemoryUserRepo implements UserRepository {
  private users: User[] = [];
  async save(user: User) { this.users.push(user); }
  async findById(id: string) { return this.users.find(u => u.id === id); }
}
```

**Rule**: Inject dependencies so you can swap real → fake in tests. No `jest.mock()` on modules if you can inject instead.

## Contract Testing

Verify producer/consumer agreements without full integration:

```typescript
// Consumer defines the contract (what it expects)
const contract = {
  GET: '/users/123',
  response: {
    status: 200,
    body: { id: Matchers.integer(), email: Matchers.email() }
  }
};

// Producer verifies it can satisfy the contract
describe('User API contract', () => {
  it('satisfies consumer contract', async () => {
    const response = await GET('/users/123');
    expect(response.status).toBe(200);
    expect(response.body.id).toBeDefined();
    expect(response.body.email).toMatch(/@/);
  });
});
```

- Use Pact for formal consumer-driven contract testing
- Run contract tests in CI before integration tests
- Contract tests catch breaking changes before they hit staging

## Mutation Testing

**Why**: Tests can pass without actually catching bugs. Mutation testing verifies tests catch real defects.

```bash
# Ruby — mutant
bundle exec mutant run --include lib --require app --use rspec -- 'MyClass'

# JS/TS — stryker
npx stryker run

# Python — mutmut
mutmut run
mutmut results
```

- Run on changed files only in CI (too slow for full suite)
- Target: >80% mutation score on critical paths
- Surviving mutants = test gaps = add assertions

## Async Test Patterns

```typescript
// Waiting for async operations
it('sends email after signup', async () => {
  await userService.register({ email: 'new@test.com' });
  // Wait for async side effect
  await waitFor(() => expect(emailService.send).toHaveBeenCalled());
});

// Fake timers for time-dependent logic
beforeEach(() => jest.useFakeTimers());
afterEach(() => jest.useRealTimers());

it('expires token after 1 hour', () => {
  const token = createToken();
  jest.advanceTimersByTime(60 * 60 * 1000 + 1);
  expect(token.isExpired()).toBe(true);
});

// Testing promises that should reject
await expect(service.doThing()).rejects.toThrow('Not authorized');
```

## Database Cleaner Strategies

### Transaction (fastest — use for unit/integration)
```ruby
# RSpec + DatabaseCleaner
config.before(:suite) { DatabaseCleaner.strategy = :transaction }
config.around(:each) { |ex| DatabaseCleaner.cleaning { ex.run } }
```
- Wraps each test in a transaction, rolls back after
- Cannot use with tests that require multiple DB connections (Capybara, async jobs)

### Truncation (slowest — use for E2E/system)
```ruby
config.before(:suite) do
  DatabaseCleaner.clean_with(:truncation)
end
config.before(:each, type: :system) do
  DatabaseCleaner.strategy = :truncation
end
```

### Deletion (moderate — use when truncation fails)
- Like truncation but uses `DELETE` — respects foreign key order
- Slower than truncation, faster than transaction when table count is low

### Rule
- Default: transaction strategy
- System/E2E/multi-connection tests: truncation
- Never let test data leak between tests

## Zero Noise Output

- Redirect test IO to StringIO, not real stderr/stdout
- Suppress deprecation warnings by fixing them (not silencing)
- No `xit`, `pending`, `skip` — delete untestable specs
- Every warning line is wasted CI output — fix it or suppress via config

## Coverage Gates

```yaml
# SimpleCov (Ruby)
SimpleCov.minimum_coverage 80

# Jest (JS)
coverageThreshold:
  global:
    branches: 80
    functions: 80
    lines: 80
    statements: 80

# pytest-cov (Python)
# pytest --cov=src --cov-fail-under=80
```

- Gate on critical paths: 100% for auth, payments, data migrations
- Global gate: 80% minimum
- Report by file to identify specific gaps

## Load and Stress Testing

### Tool Selection
| Tool | Language | Strength |
|------|---------|----------|
| k6 | JavaScript | Developer-friendly, CI integration, cloud option |
| Artillery | JavaScript/YAML | Easy config, multiple protocols |
| Locust | Python | Distributed, programmable |
| Apache Bench (ab) | CLI | Quick one-off endpoint tests |

### Test Types
```
Load test:    expected traffic (verify SLAs hold under normal conditions)
Stress test:  2-5x expected traffic (find the breaking point)
Soak test:    sustained load for hours (detect memory leaks, connection pool exhaustion)
Spike test:   sudden traffic burst (verify auto-scaling and recovery)
```

### Key Metrics
```
Throughput:     requests per second
Latency:        p50, p95, p99 response times
Error rate:     percentage of 5xx responses
Saturation:     CPU, memory, DB connections at peak
```

### Process
```
1. Establish baseline (current performance under typical load)
2. Define SLAs (p95 < 500ms, error rate < 0.1%, throughput > 100 rps)
3. Write load test scripts (k6 or equivalent)
4. Run against staging (never against production without coordination)
5. Analyze results, identify bottlenecks
6. Optimize and re-test
7. Add to CI as regression gate (optional: run on merge to main)
```
