# Template: Transactional Outbox (Publish-With-Commit)

The fix for the dual-write problem (Commandment 6): never "save state, then publish to the bus" as two separate steps — a crash in between loses or duplicates the event. Instead, write the event into an **outbox table in the same transaction** as the state change. A separate dispatcher publishes rows from the outbox and marks them sent.

## The bug this replaces (do NOT do this)

```
# DUAL WRITE — forbidden. A crash between the two lines corrupts the system.
db.save(newState)
bus.publish(event)        # if this fails or the process dies here: state changed, no event
```

## Producing: state + event in ONE transaction

```
function handleCommand(command, deps):
    event = buildEvent(command)                 # past-tense fact, full envelope

    with deps.db.transaction() as tx:           # single atomic unit
        tx.save(newStateFrom(command))          # 1. the state change
        tx.insertOutbox(                        # 2. the event, SAME transaction
            id            = event.id,
            type          = event.type,
            payload       = serialize(event),
            status        = "PENDING",
            occurredAt    = event.occurredAt
        )
    # commit is atomic: either BOTH the state and the outbox row land, or NEITHER does.
    # No bus call inside the transaction.
```

## Dispatcher: publish PENDING rows, then mark sent

A separate, independently-running dispatcher (polling loop, or change-data-capture on the outbox table) drains the outbox:

```
function dispatchLoop(deps):
    loop:
        rows = deps.db.selectOutbox(status = "PENDING", limit = BATCH)
        for row in rows:
            deps.bus.publish(deserialize(row.payload))    # at-least-once: may re-publish on retry
            deps.db.markOutbox(row.id, status = "SENT")
```

## Dispatcher notes

- **At-least-once, by design.** If the process dies after `publish` but before `markOutbox`, the row is re-published on the next loop. That is expected and safe **because every consumer is idempotent** (Commandment 7) — the event `id` de-dupes it downstream.
- **Ordering.** If per-aggregate order matters, dispatch grouped by `aggregateId` (or a partition key) so events for one entity publish in insertion order.
- **Retention.** SENT rows can be pruned or archived on a schedule; the event store / bus is the durable log, the outbox is a hand-off buffer.
- **CDC alternative.** Instead of polling, a change-data-capture stream on the outbox table achieves the same guarantee with lower latency — the invariant (write-in-transaction, publish-out-of-band) is identical.
