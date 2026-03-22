# Payment Processing Patterns

## Provider Selection

| Provider | When | PCI Level |
|----------|------|-----------|
| Stripe | Default choice, best DX, broadest features | SAQ-A (hosted fields) |
| Braintree | PayPal required, enterprise features | SAQ-A |
| Square | In-person + online unified | SAQ-A |
| Paddle/Lemon Squeezy | SaaS, handles tax/compliance as merchant of record | SAQ-A |

**Default: Stripe.** Use Paddle/Lemon Squeezy if you want the provider to handle sales tax and be the merchant of record.

## PCI Compliance

```
NEVER handle raw card numbers on your server.
Use hosted payment fields (Stripe Elements, Braintree Drop-in):
  - Card form renders in an iframe from the payment provider
  - Your server never sees the card number
  - This qualifies you for PCI SAQ-A (simplest compliance level)
```

## Payment Flow (One-Time)

```
1. Client: render payment form (Stripe Elements)
2. Client: tokenize card → payment method ID
3. Client: send payment method ID to your API
4. Server: create PaymentIntent with idempotency key
5. Server: confirm PaymentIntent (may require 3DS/SCA)
6. Server: if 3DS required → return client_secret, client handles 3DS
7. Server: on success → fulfill order, send receipt
8. Webhook: listen for payment_intent.succeeded (source of truth)
```

## Subscription Billing

```
1. Create customer in Stripe (on registration)
2. Create subscription with price ID
3. Stripe sends invoice.payment_succeeded webhook
4. On success: activate/renew subscription in your database
5. On failure: Stripe retries (smart retries over 7 days)
6. After final failure: invoice.payment_failed → downgrade/suspend

Status mapping:
  active       → full access
  past_due     → grace period (show banner, retain access)
  unpaid       → suspended (read-only access)
  canceled     → downgraded to free tier
```

### Proration
```
Upgrade mid-cycle:  charge prorated amount for remainder of period
Downgrade mid-cycle: credit prorated amount to next invoice
Stripe handles proration automatically with proration_behavior: 'create_prorations'
```

## Webhook Handling (Critical)

```
Webhooks are the source of truth for payment status, not API responses.

1. Receive webhook POST from Stripe
2. Verify signature (stripe.webhooks.constructEvent with signing secret)
3. Check idempotency: have we already processed this event ID?
4. Process the event (update subscription status, fulfill order)
5. Return 200 OK (return 200 even if processing fails — retry later via job)
6. If processing fails: enqueue a retry job, don't block the webhook response

NEVER trust client-side payment confirmations.
ALWAYS verify via webhook before fulfilling orders.
```

### Key Events to Handle
```
payment_intent.succeeded       → fulfill order, send receipt
payment_intent.payment_failed  → notify user, retry
invoice.payment_succeeded      → renew subscription
invoice.payment_failed         → grace period, notify user
customer.subscription.updated  → sync plan changes
customer.subscription.deleted  → cancel access
checkout.session.completed     → fulfill checkout
```

## Currency Handling

```
ALWAYS store amounts as integers (cents/pence), NEVER as floats.

BAD:  amount = 19.99  (floating point: 19.989999999...)
GOOD: amount = 1999   (integer cents)

Display: format using Intl.NumberFormat or equivalent locale-aware formatter
Math:    perform all calculations in cents, convert for display only
```

## Refunds

```
Full refund:    Refund entire charge amount
Partial refund: Refund specific line items or arbitrary amount
Timing:         Refunds take 5-10 business days to appear on statement

On refund:
1. Create refund in Stripe
2. Update order status in database
3. Adjust inventory if applicable
4. Send refund confirmation email
5. Handle subscription implications (if refunding a subscription payment)
```

## Testing

```
Use Stripe test mode (separate API keys, no real charges)
Test card numbers: 4242424242424242 (success), 4000000000000002 (decline)
Test webhooks: Stripe CLI (stripe listen --forward-to localhost:3000/webhooks)
Test 3DS: use test card 4000002760003184
Test subscription cycles: Stripe test clocks (simulate time advancement)
```

## Security Checklist

- [ ] Never log full card numbers (PCI violation)
- [ ] Webhook signatures verified on every request
- [ ] Idempotency keys on all payment creation requests
- [ ] Amounts stored as integers (cents), never floats
- [ ] Stripe API keys: test keys in dev, live keys in production only
- [ ] Webhook endpoint rate-limited (prevent abuse)
- [ ] Payment status determined by webhooks, not client-side
- [ ] Refund authorization: require admin approval for large amounts
