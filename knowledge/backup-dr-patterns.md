# Backup & Disaster Recovery Patterns

## Backup Strategy

| Data Type | Method | Frequency | Retention |
|-----------|--------|-----------|-----------|
| Database | Automated snapshots + WAL/binlog archiving | Continuous (PITR) | 30 days |
| File storage (S3/GCS) | Cross-region replication | Continuous | Indefinite |
| Application config | Git (infrastructure-as-code) | On change | Git history |
| Secrets/credentials | Vault snapshots | Daily | 90 days |
| Redis/cache | RDB snapshots (if persistent data) | Hourly | 7 days |

## Database Backup

### Point-in-Time Recovery (PITR)
```
PostgreSQL: Continuous WAL archiving to S3/GCS
  - Base backup: weekly full snapshot
  - WAL segments: streamed continuously
  - Recovery: restore base backup + replay WAL to any point in time

MySQL: Binary log archiving
  - Same principle: base backup + binlog replay

Managed services (RDS, Cloud SQL): enable automated backups with PITR
  - Retention: 7-35 days (configure max)
```

### Logical Backups (pg_dump / mysqldump)
```
Use for: cross-version migration, selective table restore, dev/staging seeding
Frequency: daily
Storage: compressed, encrypted, uploaded to separate storage account
Never rely solely on logical backups — too slow for large databases
```

## RTO and RPO

```
RPO (Recovery Point Objective): Maximum acceptable data loss
  - With PITR: seconds (near-zero data loss)
  - With daily backups: up to 24 hours of data loss

RTO (Recovery Time Objective): Maximum acceptable downtime
  - With hot standby: minutes
  - With backup restore: hours (depends on database size)
  - With full infrastructure rebuild: hours to days
```

Define RTO/RPO per service tier and document in the project's operational runbook.

## Backup Verification (Critical)

```
Backups that haven't been tested are not backups.

Monthly restore test:
1. Restore latest backup to a separate environment
2. Run application health checks against restored data
3. Verify data integrity (row counts, checksums on critical tables)
4. Document results (date, duration, issues found)
5. If restore fails: fix backup process immediately (P0 incident)
```

## Disaster Recovery Procedures

### Infrastructure Failure (Single Service)
```
1. Detect: health check fails, alerting triggers
2. Assess: which service is down, what's the blast radius?
3. Recover: restart service, failover to replica, or restore from backup
4. Verify: run smoke tests, check data integrity
5. Postmortem: document cause, prevention, detection improvements
```

### Database Failure
```
1. Promote read replica to primary (if available)
2. OR restore from latest PITR backup
3. Update application connection strings
4. Verify data integrity
5. Rebuild replica for future failover
```

### Complete Infrastructure Loss
```
1. Provision new infrastructure from IaC (Terraform, CloudFormation)
2. Restore database from latest backup
3. Restore file storage from cross-region replica
4. Restore secrets from vault backup
5. Deploy application
6. Update DNS
7. Verify all services operational
```

## Multi-Region Considerations

```
Active-passive: one region serves traffic, other region has replicas ready
Active-active: both regions serve traffic, data synced bidirectionally

For most SaaS apps: active-passive is sufficient and simpler.
Active-active adds conflict resolution complexity.
```

## Monitoring Backups

```
Alerts:
  - Backup job failed → Critical (immediate)
  - Backup older than expected → Warning (within 1 hour)
  - Backup storage > 80% capacity → Warning
  - Monthly restore test overdue → Warning

Dashboard:
  - Last successful backup timestamp
  - Backup size trend
  - Restore test results (last 3 months)
```
