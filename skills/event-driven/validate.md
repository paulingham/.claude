# Static Validation (Language-Neutral)

A lightweight, fast pass to run on any diff touching events **before** the full `review-checklist.md`. These are cheap, mechanical checks the agent applies by reading the diff — no runtime, no language assumptions. Each maps to a commandment. A failure here is a FAIL in the verdict table.

## 1. Event names are past-tense facts (Commandment 1)

- For each new/renamed event `type`, check the name reads as a completed fact.
- **Flag** names that are imperative/command-shaped (`MoveFunds`, `CreateOrder`, `ChargeCard`) or present/continuous (`order.settling`, `Moving`, `Processing`).
- **Heuristic:** past-tense verbs end in a completed form ("...ed", "...settled", "...moved", "...placed"); commands are bare verbs or verb-first ("Move...", "Create...", "Charge...").
- **Fix:** rewrite as the fact — `MoveFunds` → `FundsMoved`, `order.settling` → `order.settled`.

## 2. Envelope is complete (Commandments 2, 8)

- For each event construction, confirm the envelope carries **all** required fields:
  `id`, `type`, `version`, `aggregateId`, `tenantId`, `occurredAt`, `causationId`, `correlationId`, `actor`, `payload`.
- **Flag** any missing field. Missing `causationId`/`correlationId` is a Commandment 8 failure; a payload asserting multiple facts or multiple entities is a Commandment 2 failure.

## 3. No side effects inside reducer/projection code (Commandments 3, 4, 10)

- Identify reducer/projection code (functions named/shaped as `reduce`, `project`, `apply`, `fold`, or registered as an event fold).
- **Scan the body for effect signals** — language-neutral markers to look for regardless of syntax:
  - I/O: database/query/repository calls, HTTP/RPC/network clients, file access, message-bus publish/send, cache reads/writes.
  - Clock reads: "now", "today", "currentTime", "Date"/"time" constructors with no argument.
  - Randomness: uuid/guid generation, random-number calls, shuffles.
  - Side-effecting logging, metrics emit, or command dispatch.
- **Any hit ⇒ FAIL** (Commandments 3/4, and 10 if it's an effect). Fix: move it into the reactor that builds the event; pass the resulting value in via the event.

## 4. Idempotency handling is present (Commandment 7)

- For each new/changed consumer, confirm it either:
  - de-duplicates by `event.id` (or a business idempotency key) before applying effects, **or**
  - applies only a naturally-idempotent effect (upsert / set-to-value keyed by `aggregateId`).
- **Flag** consumers that apply a non-idempotent effect (charge, send, increment, append) with no dedupe. Fix: add dedupe-by-event-id, recording the processed key in the same transaction as the effect.

## Bonus (cheap, high-value)

- **Dual-write scan (Commandment 6):** flag any code path where a state save is followed by a bus publish outside a single transaction. Fix: outbox.
- **History mutation (Commandment 5):** flag update/delete/reorder against stored events. Fix: compensating event.

## Output

Emit a short pass/fail list keyed by check number, then hand off to `review-checklist.md` for the full commandment verdict table. Static-validation failures pre-populate the corresponding FAIL rows.
