# Event-Driven Review Checklist

One check per commandment, each a Gherkin scenario the agent evaluates against the diff. Run every scenario whose subject appears in the diff; mark it **PASS**, **FAIL**, or **N/A**. Any FAIL ⇒ verdict `CHANGES_REQUESTED`, citing the commandment number and the concrete fix.

```gherkin
Feature: Event-driven standard enforcement

  # ── Commandment 1 ──────────────────────────────────────────────
  Scenario: Events are named as past-tense facts
    Given a diff that introduces or renames an event type
    When I read the event's name
    Then the name reads as a fact that already happened (e.g. "FundsMoved", "order.settled")
    And it is NOT an imperative/command ("MoveFunds") or present/continuous tense ("order.settling")
    But if it is a command or present tense
    Then FAIL citing Commandment 1 and propose the past-tense fact name (e.g. "MoveFunds" → "FundsMoved")

  # ── Commandment 2 ──────────────────────────────────────────────
  Scenario: One event states exactly one fact about one entity
    Given a diff introducing or changing an event's payload
    When I inspect the payload
    Then it asserts a single fact about a single aggregateId
    But if the payload asserts more than one fact, or spans more than one entity
    Then FAIL citing Commandment 2 and propose splitting it into separate single-fact events

  # ── Commandment 3 ──────────────────────────────────────────────
  Scenario: Reducers and projections are pure
    Given a diff touching a reducer or projection
    When I inspect its body
    Then it only computes next state from (state, event) with no I/O, network, database, or bus access
    But if it performs I/O, a network/database/bus call, or side-effecting logging
    Then FAIL citing Commandment 3 and instruct moving the effect into a reactor

  # ── Commandment 4 ──────────────────────────────────────────────
  Scenario: No clock reads or randomness inside reducers/projections
    Given a diff touching a reducer or projection
    When I inspect its body
    Then it never reads the current time and never generates randomness or ids
    And any time/random value it uses arrives inside the event (e.g. event.occurredAt)
    But if it reads the clock, generates a uuid/random value inside the fold
    Then FAIL citing Commandments 3 and 4 and instruct moving that read into the reactor that builds the event

  # ── Commandment 5 ──────────────────────────────────────────────
  Scenario: Events are immutable and append-only
    Given a diff touching event persistence or an already-emitted event
    When I inspect the change
    Then existing events are only appended, never updated, reordered, or deleted
    And corrections are modelled as new compensating events
    But if the diff updates, reorders, or deletes stored events
    Then FAIL citing Commandment 5 and propose appending a compensating event instead

  # ── Commandment 6 ──────────────────────────────────────────────
  Scenario: No dual-write; state and event share one transaction
    Given a diff that changes state and emits an event
    When I inspect the write path
    Then the event is written to the outbox in the SAME transaction as the state change
    And publishing to the bus happens out-of-band via a dispatcher
    But if it saves state and then publishes to the bus in a separate step
    Then FAIL citing Commandment 6 and show the transactional-outbox pattern as the fix

  # ── Commandment 7 ──────────────────────────────────────────────
  Scenario: Consumers are idempotent
    Given a diff adding or changing a consumer
    When I inspect how it handles a message
    Then it de-duplicates by event id (or a business idempotency key) before applying effects
    But if it has no de-duplication and its effect is not naturally idempotent
    Then FAIL citing Commandment 7 and add dedupe-by-event-id (record-processed in the same transaction as the effect)

  # ── Commandment 8 ──────────────────────────────────────────────
  Scenario: Every event carries causation and correlation
    Given a diff constructing an event
    When I inspect the envelope it builds
    Then it sets causationId to the triggering message's id
    And it sets correlationId to the originating flow's id
    But if either causationId or correlationId is missing
    Then FAIL citing Commandment 8 and require both be carried through

  # ── Commandment 9 ──────────────────────────────────────────────
  Scenario: Schema changes are additive and versioned
    Given a diff changing the schema of an existing event type
    When I compare old and new field sets
    Then it only adds new optional fields and bumps the event version
    But if it removes a field, renames a field, or changes an existing field's meaning
    Then FAIL citing Commandment 9 and propose an additive, versioned change (add + version, keep old readers working)

  # ── Commandment 10 ─────────────────────────────────────────────
  Scenario: Effects live only in reactors
    Given a diff that performs an observable side effect (email, API call, charge, cross-system write, command emit)
    When I inspect where that effect is located
    Then it lives inside a reactor / process-manager
    But if the effect is in a reducer, projection, or event constructor
    Then FAIL citing Commandment 10 and instruct relocating the effect into a reactor
```

## Output

After evaluating, emit the verdict table from `SKILL.md` § Verdict Format — every commandment mapped to PASS/FAIL/N/A, every FAIL carrying its number and a concrete fix. Any FAIL ⇒ `CHANGES_REQUESTED`; otherwise `APPROVED`.
