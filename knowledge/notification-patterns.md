# Notification Patterns

## Channel Selection

| Channel | Use For | Urgency |
|---------|---------|---------|
| Email | Transactional (receipts, password reset), digests | Low-medium |
| Push notification | Time-sensitive alerts, engagement | Medium-high |
| In-app notification | Activity feed, non-urgent updates | Low |
| SMS | 2FA, critical alerts, account security | High |
| Webhook | System-to-system events | Medium |

## Email Delivery

### Provider Selection
| Provider | Strength | When |
|----------|----------|------|
| SendGrid | Deliverability, templates | General transactional + marketing |
| Postmark | Speed, transactional focus | Transactional-only (fastest delivery) |
| AWS SES | Cost at scale | High volume, already on AWS |
| Mailgun | Developer experience, EU hosting | GDPR-focused, developer-first |

### Architecture
```
Application → Background Job → Email Service → Provider API
              (never send inline — blocks the request)
```

### Template Organization
```
templates/
  layouts/
    default.html        — header, footer, branding
    plain.html          — minimal layout for transactional
  emails/
    welcome.html        — registration confirmation
    password-reset.html — password reset link
    invoice.html        — payment receipt
    digest.html         — weekly activity digest
```

Use a template engine (MJML for responsive email, Handlebars/ERB for dynamic content). Never construct HTML in code — always use templates.

### Deliverability
- Set up SPF, DKIM, and DMARC DNS records
- Use a dedicated sending domain (mail.yourdomain.com)
- Monitor bounce rate (< 2%) and complaint rate (< 0.1%)
- Process bounces and unsubscribes automatically
- Warm up new sending domains gradually

## Notification Preferences

```
User preferences table:
  user_id, channel, category, enabled, frequency

Categories:   security, billing, activity, marketing, digest
Frequencies:  immediate, daily_digest, weekly_digest, never

Rules:
- Security notifications (2FA, password change): always sent, cannot be disabled
- Marketing: opt-in only (CAN-SPAM, GDPR)
- Transactional: sent by default, can be reduced to digest
```

## Event-Driven Notification

```
Event: user.registered
  → Send welcome email (immediate)
  → Send push notification to admin (immediate)
  → Add to weekly onboarding digest (batched)

Event: payment.failed
  → Send email to user (immediate)
  → Send Slack alert to billing team (immediate)
  → Create in-app notification (immediate)
```

Use an event bus or notification service that fans out events to channels based on user preferences and notification rules.

## Unsubscribe Handling

- Every email MUST have a one-click unsubscribe link (CAN-SPAM, GDPR)
- Use List-Unsubscribe header for email client integration
- Process unsubscribe within 24 hours (preferably instantly)
- Provide a preference center (manage categories, not just all-or-nothing)
- Never re-subscribe a user without explicit consent

## Testing

```
Development: Use Mailhog, Ethereal, or LetterOpener to intercept emails locally
Testing:     Mock the email provider client, verify correct template + params
Staging:     Send to a test inbox (Mailtrap) — never to real users
Production:  Monitor delivery rates, bounce rates, complaint rates
```

## Idempotent Delivery

```
Problem:  Job retries can send duplicate emails
Solution: Track sent notifications by (user_id, event_id, channel)
          Before sending: check if already sent for this event
          After sending:  mark as sent with timestamp
```
