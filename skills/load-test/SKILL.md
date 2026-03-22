---
name: "Load Test"
description: "Performance verification phase: run load tests against staging, establish baselines, verify SLAs, detect regressions. Integrates with the pipeline after Verify."
context: fork
agent: qa-engineer
argument-hint: "Target URL and expected load (e.g., 'https://staging.app.com 100rps')"
---

# Load Test

## What This Skill Does

Runs load tests against a deployed environment to verify performance under expected and stress conditions. Establishes baselines, detects regressions, and validates SLA targets. Can be integrated as an optional pipeline phase after Verify.

## When to Invoke

- After `/verify` completes, before `/qa-test-strategy` (optional performance gate)
- Before production deployment of performance-critical changes
- When establishing initial performance baselines for a new service
- After significant architectural changes (new database queries, new caching layer)

## Process

### Step 1: Detect Load Testing Tool

| Signal | Tool | Config File |
|--------|------|------------|
| `k6` in PATH or devDependencies | k6 | `load-tests/*.js` |
| `artillery` in devDependencies | Artillery | `load-tests/*.yml` |
| `locust` in requirements | Locust | `locustfile.py` |
| None found | k6 (recommend install) | Generate from scratch |

### Step 2: Define Test Scenarios

```markdown
## Load Test Scenarios

### Smoke (sanity check)
- 1 virtual user, 30 seconds
- Verify: all endpoints respond, no errors

### Load (expected traffic)
- Target RPS from requirements (e.g., 100 rps)
- Ramp: 0 → target over 1 minute, hold 3 minutes, ramp down 30 seconds
- Verify: p95 < 500ms, error rate < 0.1%

### Stress (find breaking point)
- Ramp: 0 → 2x target over 2 minutes, hold 2 minutes
- Monitor: at what point does p95 exceed 1s? Error rate exceed 1%?
- Document the breaking point

### Soak (optional, for memory leak detection)
- Sustained load at 50% target for 30 minutes
- Monitor: memory growth, connection pool, response time drift
```

### Step 3: Generate/Run Tests

**k6 example:**
```javascript
import http from 'k6/http';
import { check, sleep } from 'k6';

export const options = {
  stages: [
    { duration: '1m', target: 100 },  // Ramp up
    { duration: '3m', target: 100 },  // Hold
    { duration: '30s', target: 0 },   // Ramp down
  ],
  thresholds: {
    http_req_duration: ['p(95)<500'],  // 95% under 500ms
    http_req_failed: ['rate<0.01'],    // Error rate < 1%
  },
};

export default function () {
  const res = http.get(`${__ENV.BASE_URL}/api/v1/resources`);
  check(res, { 'status 200': (r) => r.status === 200 });
  sleep(1);
}
```

Run: `k6 run --env BASE_URL=https://staging.app.com load-tests/load.js`

### Step 4: Analyze Results

```markdown
## Load Test Results

### Summary
- Duration: [total test time]
- Peak VUs: [max virtual users]
- Total requests: [count]

### Performance
| Metric | Value | SLA Target | Status |
|--------|-------|-----------|--------|
| p50 latency | [ms] | < 200ms | PASS/FAIL |
| p95 latency | [ms] | < 500ms | PASS/FAIL |
| p99 latency | [ms] | < 1000ms | PASS/FAIL |
| Error rate | [%] | < 0.1% | PASS/FAIL |
| Throughput | [rps] | > [target] | PASS/FAIL |

### Bottlenecks Identified
- [e.g., Database query on /api/v1/search takes 800ms at 50 rps]
- [e.g., Connection pool exhausted at 150 rps]

### Recommendations
- [e.g., Add database index on search_vector]
- [e.g., Increase connection pool from 10 to 25]
```

### Step 5: Baseline Management

```
First run:  save results as baseline (store in load-tests/baselines/)
Future runs: compare against baseline
Regression: p95 increased > 20% from baseline → WARNING
            p95 increased > 50% from baseline → FAIL
```

## Phase Output

```
Verdict: PERFORMANCE_VERIFIED / PERFORMANCE_WARNING / PERFORMANCE_FAILED
Next: Fix bottlenecks and re-test / Proceed to deployment
Artifacts: [k6/Artillery report, baseline comparison, bottleneck analysis]
Metrics: { p50: Nms, p95: Nms, p99: Nms, error_rate: N%, throughput: N rps }
```
