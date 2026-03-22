# Data Privacy Patterns (GDPR / CCPA / Privacy)

## Data Classification

| Category | Examples | Handling |
|----------|---------|----------|
| PII (Personally Identifiable) | Email, name, phone, address, IP | Encrypt at rest, access-controlled |
| Sensitive PII | SSN, passport, health data, financial | Encrypt, audit access, minimize retention |
| Non-personal | Aggregated analytics, system logs (no user IDs) | Standard handling |
| Public | Published content, public profiles | No special handling |

## Privacy by Design Principles

```
1. Data minimization:  Collect only what you need for the stated purpose
2. Purpose limitation:  Use data only for the purpose it was collected
3. Storage limitation:  Delete data when the purpose is fulfilled
4. Consent:            Obtain explicit consent before processing
5. Transparency:       Tell users what data you collect and why
```

## Consent Management

```
Consent types:
  - Necessary:    Session cookies, security — no consent needed
  - Functional:   Preferences, language — legitimate interest
  - Analytics:    Usage tracking, performance — requires consent
  - Marketing:    Email campaigns, retargeting — requires explicit opt-in

Implementation:
  - Present cookie banner with granular options (not just "accept all")
  - Record consent: user_id, consent_type, granted (bool), timestamp, version
  - Allow withdrawal at any time (as easy as granting)
  - Re-consent when privacy policy changes (track policy version)
```

## Right to Erasure (Data Deletion)

### Deletion Request Flow
```
1. User requests deletion (settings page or email to support)
2. Verify identity (require password confirmation or email verification)
3. Enqueue deletion job (background, may take up to 30 days per GDPR)
4. Delete or anonymize all personal data:
   - User record: anonymize (replace PII with hashes, keep non-PII for analytics)
   - User-generated content: delete or anonymize per policy
   - Backups: document retention period, note that backups expire naturally
   - Third-party systems: trigger deletion via API (Stripe, analytics, etc.)
5. Confirm deletion to user via email (sent before account deletion)
6. Log deletion event (what was deleted, when — for compliance audit)
```

### Anonymization vs Deletion
```
Anonymize when: you need to keep records for analytics/reporting
  - Replace name with "Deleted User #12345"
  - Replace email with hash (SHA-256)
  - Keep: created_at, aggregated metrics, non-PII
  - Delete: name, email, phone, address, IP addresses

Hard delete when: no business reason to keep any trace
  - CASCADE delete all associated records
  - Remove from search indexes
  - Remove from CDN/cache
```

## Right to Data Portability (Data Export)

```
1. User requests export (settings page)
2. Enqueue export job (may be large)
3. Generate machine-readable export (JSON or CSV):
   - Profile data
   - Content they created
   - Activity history
   - Preferences and settings
4. Package as ZIP, upload to secure storage
5. Send download link via email (signed URL, expires in 48h)
6. Delete export file after download or expiry
```

## Data Retention Policies

| Data Type | Retention | After Expiry |
|-----------|-----------|-------------|
| Active user data | While account active | Anonymize on account deletion |
| Inactive accounts | 24 months of inactivity | Notify, then delete after 30 days |
| Server logs | 90 days | Auto-delete |
| Analytics events | 24 months | Aggregate and delete raw events |
| Payment records | 7 years (tax/legal) | Keep anonymized |
| Support tickets | 3 years | Anonymize |
| Audit logs | 7 years | Keep (no PII in audit logs) |

### Implementation
```
- Automated retention job runs nightly
- Queries for records past retention period
- Anonymizes or deletes per policy
- Logs actions for compliance audit
```

## PII in Logs and Monitoring

```
NEVER log: passwords, tokens, credit card numbers, SSN
REDACT in logs: email → "u***@example.com", IP → "192.168.x.x"
Safe to log: user_id (UUID), request_id, timestamps, actions

Configure log sanitizer middleware:
  - Pattern match and redact known PII fields
  - Use structured logging (key-value) to make redaction reliable
  - Audit log configuration periodically
```

## Cookie Compliance

```
Necessary cookies (no consent required):
  - Session cookie (httpOnly, Secure)
  - CSRF token
  - Cookie consent preference itself

Consent-required cookies:
  - Analytics (Google Analytics, Mixpanel)
  - Marketing/advertising pixels
  - Third-party integrations

Implementation:
  - Don't set consent-required cookies until consent is given
  - Provide "reject all" option (not just "accept all")
  - Remember consent in a necessary cookie (not a consent-required one)
```

## Security Checklist

- [ ] PII encrypted at rest (database-level or field-level encryption)
- [ ] Data access logged for audit trail
- [ ] Retention policies automated (not manual)
- [ ] Deletion request flow implemented and tested
- [ ] Data export flow implemented and tested
- [ ] Cookie consent banner with granular controls
- [ ] PII redacted from logs and error reports
- [ ] Third-party data processors documented (DPA in place)
- [ ] Privacy policy updated when data practices change
- [ ] Consent records stored with timestamps and policy version
