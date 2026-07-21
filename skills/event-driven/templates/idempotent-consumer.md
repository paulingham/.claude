# Template: Idempotent Consumer (Dedupe by Event Id)

Delivery is **at-least-once** (Commandment 7): the same event *will* eventually arrive twice — from an outbox re-publish, a broker redelivery, or a consumer restart. A consumer must make double-processing harmless by de-duplicating on the event `id` (or a business idempotency key).

## Pseudocode

```
function consume(event, deps):
    key = event.id                    # or a business idempotency key from the payload

    # 1. Have we already handled this exact event? Ask the dedupe store.
    if deps.dedupe.seen(key):
        return ACK                     # already processed — ACK and do nothing else

    # 2. Do the work and record the key ATOMICALLY, so a crash can't leave
    #    "work done but key unrecorded" (which would reprocess) OR
    #    "key recorded but work not done" (which would silently drop).
    with deps.db.transaction() as tx:
        applyEffect(event, tx)         # the actual handling
        tx.recordProcessed(key)        # mark this event id as done, same tx

    return ACK
```

## Rules

- **Dedupe key = `event.id`** by default (guaranteed unique per event by the envelope). Use a business idempotency key only when the same logical action can arrive under different event ids.
- **Record-processed and do-the-work in one transaction.** If they are separate steps, a crash between them reintroduces the exact bug you are trying to prevent.
- **Naturally-idempotent effects need no store.** An upsert keyed by `aggregateId`, or a `SET status = 'shipped'`, is safe to repeat — then the dedupe store is optional. Reach for the dedupe table when the effect is *not* naturally repeatable (charging a card, sending an email, incrementing a counter).
- **ACK on duplicate.** A duplicate is success, not failure — ACK it so the broker stops redelivering.
- **Dedupe store retention.** Keep processed keys long enough to cover the broker's maximum redelivery window; older keys can be pruned.
