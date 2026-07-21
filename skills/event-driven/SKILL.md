---
name: event-driven
description: The event-driven architecture standard for this codebase. Invoke whenever creating or editing events, event schemas/envelopes, reducers/projections, reactors/process-managers, sagas, the transactional outbox, or message consumers — and whenever REVIEWING a diff that touches any of those. Enforces the Ten Commandments, generates code from the templates in the project's own language, and blocks merges that violate a commandment.
---

# Event-Driven Architecture Standard

This skill is the single source of truth for how this codebase does event-driven work. It is **language-agnostic**: it prescribes patterns and checks, not a runtime, framework, or serialization library. When it generates code, it generates it in whatever language the target project already uses, following that project's idioms.

## When to Use

Fire this skill when the work touches events in any form:

- **Creating or editing an event** — a new event type, a payload change, a new version.
- **Event schemas / envelopes** — defining or altering the shape of events on the wire or in the store.
- **Reducers / projections** — folding events into state or read models.
- **Reactors / process-managers / sagas** — code that reacts to an event by doing something (side effects, new commands).
- **The outbox** — publishing events atomically with a state change.
- **Consumers** — anything that subscribes to and processes events.
- **Reviewing any of the above** — run the review checklist against the diff before it merges.

## When NOT to Use

- Pure request/response CRUD with no events, no bus, no event store, and no projection.
- Synchronous, in-process function calls that are not modelled as events.
- Read-only reporting that queries live tables directly and never subscribes to a stream.

If in doubt and the change adds or renames a message that other code subscribes to, it *is* an event — use this skill.

## The Four Roles

Every piece of event-driven code is exactly one of these. Keep them separate; never let one role do another's job.

| Role | Question it answers | Rule |
|------|---------------------|------|
| **Command** | "Please do X." | An imperative request that may be rejected. Names a *wish*, not a fact. May fail validation. |
| **Event** | "X happened." | An immutable, past-tense *fact*. Cannot be rejected — it already occurred. Never mutated, never deleted. |
| **Reducer** | "Given the facts so far, what is the state?" | A **pure** function `(state, event) → state`. No effects. Deterministic. |
| **Reactor** | "Now that X happened, what should I do?" | Reacts to events by performing effects and/or issuing new commands. All I/O lives here. Also called process-manager or saga. |

A command *may* produce an event. An event *may* be folded by a reducer and *may* trigger a reactor. A reactor *may* emit new commands. State is derived from events, never the other way round.

## The Ten Commandments

These are verbatim and authoritative. Every check, template, and review verdict traces back to a numbered commandment.

1. **Name every event as a past-tense fact.** An event records something that already happened (`FundsMoved`, `order.settled`). Never a command or the present/imperative tense (`MoveFunds`, `order.settling`). The name is a fact about the past, not a wish for the future.

2. **One event states exactly one fact about exactly one entity.** An event asserts a single fact about a single aggregate. If the payload carries more than one fact, or spans more than one entity, split it into separate events.

3. **Reducers and projections are pure.** A reducer is a deterministic function of `(state, event)`. No I/O, no network, no database, no message bus, no logging with side effects — nothing but computing the next state from the inputs it was given.

4. **No clock reads and no randomness inside a reducer or projection.** Time and randomness are inputs, not ambient reads. If state depends on "now" or on a random value, that value must arrive *inside the event* (set by the reactor/command handler that produced it), never read from the environment during the fold.

5. **Events are immutable and append-only.** Once written, an event is never updated, reordered, or deleted. Correcting a mistake means appending a new compensating event, not editing history.

6. **Never dual-write state and the bus.** Do not commit a state change to the database and then, in a separate step, publish to the bus — a crash between the two loses or duplicates the event. Persist the event in the **same transaction** as the state change via the transactional outbox, and let a separate dispatcher publish it.

7. **Every consumer is idempotent.** Delivery is at-least-once. A consumer must de-duplicate by event id (or a business idempotency key) so that processing the same event twice has the same effect as processing it once.

8. **Every event carries its causation and correlation.** Each event records the id of the message that caused it (`causationId`) and the id of the originating request/flow it belongs to (`correlationId`), so any effect can be traced end-to-end.

9. **Schema changes are additive and versioned.** Never remove or rename a field on an existing event, and never change the meaning of an existing field. Add new optional fields and bump the event `version`. Old consumers must keep working against old events forever.

10. **Effects live only in reactors.** Sending email, calling an API, charging a card, writing to another system, issuing a command — any observable side effect — happens in a reactor, never in a reducer, a projection, or an event constructor.

## How to Apply

When this skill is active, do the following.

### (a) Generate code from the templates — in the project's own language

The `templates/` directory holds language-neutral patterns. Do **not** paste the pseudocode. Instead:

1. Detect the target project's language, idioms, and existing serialization/validation approach from the surrounding code.
2. Translate the relevant template into that language, honouring the project's naming conventions, error handling, and test framework.
3. Preserve every invariant the template's notes call out (purity, past-tense naming, envelope completeness, outbox-in-transaction, dedupe-by-id).

Templates:

- `templates/event-envelope.md` — the canonical envelope every event carries.
- `templates/reducer.md` — a pure reducer (bans I/O, clock reads, randomness).
- `templates/reactor.md` — a reactor / process-manager (effects live here).
- `templates/outbox.md` — transactional outbox (publish-with-commit) + dispatcher.
- `templates/idempotent-consumer.md` — dedupe-by-event-id consumer.

### (b) Run the review checklist on any diff touching events

For every diff that adds or changes events, envelopes, reducers, projections, reactors, sagas, the outbox, or consumers, evaluate `review-checklist.md` — one Gherkin scenario per commandment — against the diff. Also run `validate.md` for the fast static checks (past-tense names, complete envelope, no effects in reducers, idempotency present).

### (c) Block merges that violate a commandment

Produce a verdict table mapping each of the Ten Commandments to **PASS**, **FAIL**, or **N/A**.

- If any commandment is **FAIL**, the review verdict is **CHANGES_REQUESTED** — the diff must not merge.
- Every **FAIL** line MUST cite the commandment number and give a concrete fix (e.g. "Commandment 1: rename `MoveFunds` → `FundsMoved`", "Commandment 6: wrap the insert + publish in one transaction via the outbox").
- **N/A** is only valid when the diff genuinely does not exercise that commandment; state why.

### Verdict Format

```
Event-Driven Review — <path or PR>
| # | Commandment                                   | Verdict | Note / Fix |
|---|-----------------------------------------------|---------|------------|
| 1 | Past-tense fact names                         | PASS    |            |
| 2 | One fact / one entity per event               | PASS    |            |
| 3 | Pure reducers & projections                   | FAIL    | Reducer at foo.x reads the DB — move the lookup into the reactor that builds the event. |
| 4 | No clock/randomness in reducers               | PASS    |            |
| 5 | Events immutable & append-only                | PASS    |            |
| 6 | No dual-write; use the outbox                 | FAIL    | insert() then publish() — wrap both in one tx via the outbox. |
| 7 | Idempotent consumers                          | N/A     | No consumer in this diff. |
| 8 | Causation + correlation carried               | PASS    |            |
| 9 | Additive, versioned schema changes            | PASS    |            |
| 10| Effects only in reactors                      | PASS    |            |

Verdict: CHANGES_REQUESTED (Commandments 3, 6)
```

If every applicable commandment is PASS, the verdict is **APPROVED**.

## Anti-Patterns

- **Reducer that "just logs" or "just reads the current time"** — still a violation (Commandments 3, 4). Pass the value in via the event.
- **"I'll publish after the commit, it's basically atomic"** — it is not (Commandment 6). Use the outbox.
- **Renaming a field "because no one uses the old name"** — breaks replay of historical events (Commandments 5, 9). Add + version instead.
- **A consumer that trusts the broker for exactly-once** — no broker gives you that end-to-end (Commandment 7). Dedupe by id yourself.
