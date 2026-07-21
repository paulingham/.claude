# Template: Pure Reducer

A reducer folds events into state: `(state, event) → state`. It is a **pure function**. Translate this pseudocode into the target language as a plain function (or a method with no dependencies) — never a class that holds a connection, clock, or client.

## Pseudocode

```
function reduce(state, event):
    switch event.type:

        case "AccountOpened":
            return state.with(
                id       = event.aggregateId,
                balance  = 0,
                openedAt = event.occurredAt,     # time comes FROM the event
                status   = "open"
            )

        case "FundsDeposited":
            return state.with(
                balance = state.balance + event.payload.amount
            )

        case "FundsWithdrawn":
            return state.with(
                balance = state.balance - event.payload.amount
            )

        default:
            return state          # unknown/older event types: no change

# Rebuild current state by folding the whole stream:
function project(events):
    state = EMPTY_STATE
    for event in events:
        state = reduce(state, event)
    return state
```

## Banned inside a reducer or projection (Commandments 3 & 4)

- **No I/O** — no database reads/writes, no HTTP, no file access, no message bus, no cache.
- **No clock reads** — never call "now"/"today". Use `event.occurredAt` (or a timestamp inside the payload).
- **No randomness** — never generate a uuid, random number, or shuffle. If an id is needed, it must already be in the event.
- **No mutation of shared state** — return a new state value; do not mutate globals or the input in place.
- **No logging with side effects, no metrics emit, no throwing on "business" conditions** — a malformed event is a producer bug caught upstream, not something the fold reaches out to report.

## Why

Purity makes the reducer **replayable** and **deterministic**: folding the same events always yields the same state, on any machine, at any time. The moment a reducer reads the clock or the network, replay stops being reproducible. Anything a reducer seems to "need" from the outside must instead be captured into the event by the reactor/command handler that produced it — see `reactor.md`.
