# Template: Reactor / Process-Manager

A reactor reacts to an event by doing something: performing side effects and/or issuing new commands. **All I/O lives here** — this is the home for everything a reducer is forbidden to touch (Commandment 10). Also called a process-manager or saga when it coordinates a multi-step flow.

## Pseudocode

```
function onFundsWithdrawn(event, deps):
    # deps carries the outside world: clients, clock, id generator, command bus.
    # Effects ARE allowed here — that is the whole point of a reactor.

    if event.payload.amount > LARGE_TXN_THRESHOLD:
        deps.notifier.sendFraudReview(event.aggregateId)      # side effect: I/O

    # Issue a follow-up command. Note how we build the NEXT message so the
    # reducer downstream never has to read the clock or invent an id:
    command = MakeCommand(
        type          = "RecordLedgerEntry",
        aggregateId   = event.aggregateId,
        occurredAt    = deps.clock.now(),          # clock read happens HERE, not in a reducer
        id            = deps.ids.newId(),          # randomness/id-gen happens HERE
        causationId   = event.id,                  # this event caused the command
        correlationId = event.correlationId,       # same flow
        actor         = event.actor,
        payload       = { amount: event.payload.amount }
    )
    deps.commandBus.send(command)
```

## Process-manager (saga) shape

When a reactor spans multiple steps, it keeps its own small state machine and reacts to each step's event:

```
function onOrderPlaced(event, deps):        deps.payments.charge(...); markState("charging")
function onPaymentCaptured(event, deps):    deps.shipping.dispatch(...); markState("shipping")
function onPaymentFailed(event, deps):      deps.commandBus.send(CancelOrder(...)); markState("cancelled")
```

## Rules

- **This is where effects belong** — network calls, emails, charges, writes to other systems, emitting commands. A reducer/projection doing any of these is a Commandment 3/10 violation; move it here.
- **Reactors produce the values reducers must not read.** The clock read, the id/uuid generation, the random choice — do them in the reactor and bake the result into the event or command, so the fold stays pure (Commandments 4).
- **Reactors must themselves be idempotent** when they subscribe to a stream — the same event may be delivered twice (Commandment 7). Guard effects by event id, or make them naturally idempotent.
- **Reactors carry causation/correlation forward** — copy `correlationId` from the triggering event and set `causationId` to the triggering event's `id` (Commandment 8).
