# State Machine Patterns

## When to Use a State Machine

```
Use when:
  - An entity has distinct states with rules about valid transitions
  - Business logic depends on "what state are we in?"
  - You need an audit trail of state changes
  - Multiple actors can trigger transitions (user, admin, system, scheduler)

Examples:
  - Order: draft → submitted → paid → shipped → delivered → returned
  - Task: todo → in_progress → blocked → review → done → archived
  - Subscription: trial → active → past_due → canceled → expired
  - User: pending → active → suspended → deleted
```

## Design Principles

### 1. States are Explicit
```
Store state as a string/enum column, not derived from other fields.

BAD:  "active" = has_paid && !canceled_at && !suspended
GOOD: status enum: active, canceled, suspended (single source of truth)
```

### 2. Transitions are Guarded
```
Not every state can reach every other state. Define allowed transitions:

Order:
  draft      → [submitted]
  submitted  → [paid, canceled]
  paid       → [shipped, refunded]
  shipped    → [delivered, returned]
  delivered  → [returned]
  canceled   → []  (terminal)
  refunded   → []  (terminal)
```

### 3. Side Effects are Triggered by Transitions
```
On transition from submitted → paid:
  - Send payment confirmation email
  - Enqueue fulfillment job
  - Update analytics

Side effects are NOT triggered by setting the state directly.
They are triggered by the transition event.
```

## Implementation

### Framework Selection
| Stack | Library | Features |
|-------|---------|----------|
| Ruby | AASM, Statesman | Callbacks, guards, audit trail |
| Node.js | xstate, javascript-state-machine | Hierarchical states, actors |
| Python | transitions, django-fsm | Guards, callbacks, diagram generation |
| Go | looplab/fsm | Simple, lightweight |

### Basic Pattern (No Library)

```typescript
// Define valid transitions
const TRANSITIONS: Record<string, string[]> = {
  draft: ['submitted'],
  submitted: ['paid', 'canceled'],
  paid: ['shipped', 'refunded'],
  shipped: ['delivered', 'returned'],
  delivered: ['returned'],
  canceled: [],
  refunded: [],
};

class Order {
  transitionTo(newState: string): void {
    const allowed = TRANSITIONS[this.status];
    if (!allowed?.includes(newState)) {
      throw new InvalidTransitionError(this.status, newState);
    }
    const oldState = this.status;
    this.status = newState;
    this.onTransition(oldState, newState);
  }

  private onTransition(from: string, to: string): void {
    if (from === 'submitted' && to === 'paid') {
      SendConfirmationEmailJob.performAsync(this.id);
      EnqueueFulfillmentJob.performAsync(this.id);
    }
  }
}
```

### Rails (AASM)
```ruby
class Order < ApplicationRecord
  include AASM

  aasm column: :status do
    state :draft, initial: true
    state :submitted, :paid, :shipped, :delivered, :canceled, :refunded

    event :submit do
      transitions from: :draft, to: :submitted
    end

    event :pay do
      transitions from: :submitted, to: :paid,
                  after: [:send_confirmation, :enqueue_fulfillment]
    end

    event :cancel do
      transitions from: [:draft, :submitted], to: :canceled
      guard { cancelable? }
    end
  end
end
```

### Django (django-fsm)
```python
from django_fsm import FSMField, transition

class Order(models.Model):
    status = FSMField(default='draft')

    @transition(field=status, source='draft', target='submitted')
    def submit(self):
        pass  # Side effects in signal handlers or post-transition hooks

    @transition(field=status, source='submitted', target='paid')
    def pay(self):
        self.paid_at = timezone.now()
```

## Audit Trail

```
Every state transition should be recorded:

state_transitions table:
  id, entity_type, entity_id, from_state, to_state, triggered_by, metadata, created_at

Record:
  - Who triggered it (user_id, system, scheduler)
  - When it happened (timestamp)
  - Why (reason/metadata — e.g., "Payment received via Stripe webhook pi_123")
  - Any guard conditions that were evaluated
```

### Implementation
```ruby
# After every transition:
StateTransition.create!(
  entity: order,
  from_state: old_state,
  to_state: new_state,
  triggered_by: Current.user || 'system',
  metadata: { payment_id: payment.id }
)
```

## Guards (Conditional Transitions)

```
Guards prevent transitions when conditions are not met:

  cancel:
    from: submitted → canceled
    guard: no_payment_in_progress?
    guard: within_cancellation_window?

  ship:
    from: paid → shipped
    guard: inventory_available?
    guard: shipping_address_valid?

If any guard fails, the transition is rejected with a clear error message.
```

## Testing State Machines

```
Test every valid transition:
  it "transitions from draft to submitted"
  it "transitions from submitted to paid"

Test every invalid transition:
  it "cannot transition from draft to paid"
  it "cannot transition from canceled to anything"

Test guards:
  it "cannot cancel after payment window"
  it "cannot ship without inventory"

Test side effects:
  it "sends confirmation email on payment"
  it "creates audit trail entry on every transition"

Test terminal states:
  it "has no transitions from canceled"
  it "has no transitions from refunded"
```

## Anti-Patterns

```
- God state: a "processing" state that means 5 different things — split into specific states
- Missing terminal states: every workflow needs at least one end state
- Direct state assignment: order.status = 'paid' bypasses guards and side effects — always use transition methods
- State in multiple places: status column AND boolean flags (is_paid, is_shipped) — pick one source of truth
- No audit trail: you will always need to answer "how did it get into this state?"
```
