# Feature Flag Patterns

## Flag Types

| Type | Purpose | Lifetime | Example |
|------|---------|----------|---------|
| Release | Gate incomplete features | Days-weeks | `new_checkout_flow` |
| Experiment | A/B test variants | Weeks-months | `pricing_page_variant` |
| Ops | Circuit breaker, kill switch | Permanent | `enable_search_indexing` |
| Permission | User-tier gating | Permanent | `premium_dashboard` |

## Provider Selection

| Provider | Type | When |
|----------|------|------|
| LaunchDarkly | Hosted | Enterprise, real-time updates, advanced targeting |
| Unleash | Self-hosted/cloud | Open source, privacy-first |
| Flipper | Ruby gem | Rails apps, simple setup |
| GrowthBook | Self-hosted/cloud | A/B testing focus, open source |
| Custom (DB-backed) | Self-built | Simple on/off flags, no targeting needed |

## Implementation Pattern

### Basic Flag Check
```
// Simple boolean flag
if (featureFlags.isEnabled('new_checkout')) {
  renderNewCheckout();
} else {
  renderOldCheckout();
}
```

### With Targeting Rules
```
// Percentage rollout
flag: new_checkout
  - 10% of users (canary)
  - 100% of internal users (dogfood)
  - 50% of users in US (A/B test)
  - specific user IDs (beta testers)
```

### Architecture
```
Application startup → fetch flag configuration (cache locally)
On flag check → evaluate rules against user context
Background → poll for flag changes (30s interval) or use streaming
```

## Flag Lifecycle

```
1. CREATE:   Developer adds flag (disabled by default)
2. DEVELOP:  Code behind flag, deploy to production (dark launch)
3. ENABLE:   Enable for internal users / beta testers
4. ROLLOUT:  Gradually increase percentage (10% → 50% → 100%)
5. CLEANUP:  Remove flag from code after 100% rollout (mandatory!)
```

### Cleanup (Critical)
```
Stale flags are tech debt. Track flag age and enforce cleanup:
- Release flags: remove within 2 weeks of 100% rollout
- Experiment flags: remove within 1 week of decision
- Set a "remove by" date when creating the flag
- CI check: warn on flags older than their remove-by date
```

## Testing with Flags

```
Test BOTH paths (flag on AND flag off):
  describe('checkout', () => {
    it('renders new checkout when flag enabled', () => {
      withFlag('new_checkout', true);
      // assert new checkout renders
    });
    it('renders old checkout when flag disabled', () => {
      withFlag('new_checkout', false);
      // assert old checkout renders
    });
  });

E2E: test the default state (flag off) + the enabled state
Never leave tests that only test one path — the other path is production code too
```

## A/B Testing

```
1. Define hypothesis: "New pricing page increases conversion by 10%"
2. Create experiment flag with variants: control (A), treatment (B)
3. Assign users to variant (deterministic hash of user_id + experiment_name)
4. Track events: page_view, click_cta, conversion
5. Analyze: statistical significance (p < 0.05, minimum sample size)
6. Decide: ship winner, remove flag
```

### Event Tracking
```
trackEvent({
  event: 'pricing_page_cta_click',
  user_id: user.id,
  variant: featureFlags.getVariant('pricing_experiment'),
  timestamp: new Date(),
});
```

## Anti-Patterns

```
- Flag in flag: nesting flags creates exponential test complexity
- Long-lived release flags: if it's been flagged for > 1 month, it's tech debt
- Flags as permissions: use RBAC for access control, not feature flags
- Flags in database queries: filter in application code, not SQL
- No default: always provide a default (flag off) for when the flag service is unavailable
```
