# Template: Event Envelope

The canonical wrapper every event carries. This is a **language-neutral field schema** — implement it idiomatically in the target project's language (a struct/record/class, a dataclass, an interface, a schema object — whatever the codebase already uses for messages), and serialize it with whatever the project already uses.

## Fields

| Field | Type (neutral) | Required | Meaning |
|-------|----------------|----------|---------|
| `id` | unique id (uuid/ulid) | yes | This event's own unique identity. The dedupe key for idempotent consumers (Commandment 7). |
| `type` | string | yes | The past-tense fact name, e.g. `FundsMoved`, `order.settled` (Commandment 1). |
| `version` | integer | yes | Schema version of this event `type`. Bumped on additive change (Commandment 9). |
| `aggregateId` | id | yes | The single entity this fact is about (Commandment 2). |
| `tenantId` | id | yes | Owning tenant / partition. Present even in single-tenant systems so multi-tenancy is a config change, not a schema change. |
| `occurredAt` | timestamp | yes | When the fact happened, set by the producer. This is the event's time — reducers read it from here, never from the clock (Commandment 4). |
| `causationId` | id | yes | The id of the message (command or event) that directly caused this event (Commandment 8). |
| `correlationId` | id | yes | The id of the originating request/flow this event belongs to; constant across a whole causal chain (Commandment 8). |
| `actor` | id / descriptor | yes | Who or what caused this — a user id, service name, or system principal. |
| `payload` | object | yes | The single fact's data (Commandment 2). Contains only fields describing *this* fact about *this* entity. |

## Notes

- **Implement idiomatically.** In one language this is a frozen dataclass; in another a sealed record; in another a validated schema object. Do not invent a new serialization format — match the project.
- **Envelope vs payload.** Envelope fields are cross-cutting metadata every event shares. `payload` is event-specific. Keep causation/correlation/actor in the envelope, never buried in the payload.
- **Ids are opaque.** Generate `id` at construction time. `correlationId` is copied from the triggering message (or equals `id` for a root event). `causationId` is the triggering message's `id`.
- **Time is data.** `occurredAt` is set once by the producer and is then immutable (Commandment 5). Downstream code treats it as a value, never re-reads "now".
