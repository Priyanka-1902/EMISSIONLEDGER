# Incident Response Runbook

## Severity Levels

| Severity | Definition | Response Time | Examples |
|---|---|---|---|
| P1 — Critical | Platform down; data breach suspected; CBAM report corruption | 15 min | DB unreachable; auth service down; audit chain broken |
| P2 — High | Feature unavailable; calculation errors affecting >1 tenant | 1 hour | Report generation failed; CBAM XML invalid |
| P3 — Medium | Degraded performance; single-tenant issue | 4 hours | Slow dashboard; ingestion job stuck |
| P4 — Low | Minor issues; cosmetic bugs | Next business day | UI rendering issue; non-critical error |

## On-Call Rotation

- Primary: Rotating weekly via PagerDuty
- Escalation chain: On-call engineer → CTO → CEO (for P1 data breach)
- PagerDuty integration: GitHub Actions, CloudWatch alarms, Sentry

## P1 Response Playbook

### Step 1: Acknowledge (< 5 min)
```bash
# Acknowledge PagerDuty alert
# Join incident Slack channel #incidents-live
# Identify blast radius: how many tenants affected?
```

### Step 2: Assess (< 15 min)
```bash
# Check overall service health
kubectl get pods -n emissionledger -o wide

# Check recent deployments
kubectl rollout history deployment/emissionledger-calculation

# Check for data breach indicators
aws cloudtrail lookup-events \
  --lookup-attributes AttributeKey=EventName,AttributeValue=GetObject \
  --start-time $(date -d '1 hour ago' -u +%Y-%m-%dT%H:%M:%SZ) \
  --region ap-south-1

# Check audit log chain integrity
curl -X POST https://api.emissionledger.in/v1/audit/verify-chain \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -d '{"tenant_id": "all"}'
```

### Step 3: Contain (< 30 min)

**If deployment caused the issue:**
```bash
# Rollback to previous stable version via Argo Rollouts
kubectl argo rollouts undo rollout/emissionledger-calculation
kubectl argo rollouts status rollout/emissionledger-calculation
```

**If data breach suspected:**
```bash
# Immediately revoke all active sessions
aws cognito-idp admin-user-global-sign-out \
  --user-pool-id $COGNITO_POOL_ID \
  --username $AFFECTED_USER  # or bulk via Lambda

# Enable WAF emergency block rule
aws wafv2 update-rule-group --emergency-block=true

# Notify CISO and legal team immediately
# DPDP Act 2023: breach notification required within 72 hours
```

**If DB unreachable:**
```bash
# Check RDS status
aws rds describe-db-instances --db-instance-identifier emissionledger-prod-postgres

# Force failover to standby (Multi-AZ)
aws rds reboot-db-instance \
  --db-instance-identifier emissionledger-prod-postgres \
  --force-failover
```

### Step 4: Investigate

```bash
# Pull structured logs from CloudWatch
aws logs filter-log-events \
  --log-group-name /emissionledger/prod/calculation \
  --start-time $(date -d '2 hours ago' +%s)000 \
  --filter-pattern "ERROR"

# Check Sentry for exception traces
# Grafana: review request error rate, latency, DB connection pool

# Verify CBAM calculation integrity (spot check)
python scripts/verify_calculation_sample.py --tenant-id $TENANT_ID --sample-size 50
```

### Step 5: Resolve & Recover

### Step 6: Post-Incident Review (within 48 hours)
- Write blameless post-mortem
- 5-whys root cause analysis
- Action items with owners and deadlines
- Update runbook if gaps found

## Data Recovery Runbook

### Point-in-Time Recovery
```bash
# RDS PITR to 5 minutes before incident
aws rds restore-db-instance-to-point-in-time \
  --source-db-instance-identifier emissionledger-prod-postgres \
  --target-db-instance-identifier emissionledger-prod-postgres-recovery \
  --restore-time 2024-03-15T10:25:00Z \
  --region ap-south-1

# Verify recovered data
psql $RECOVERY_DATABASE_URL -c "SELECT COUNT(*) FROM emission_records WHERE created_at > '2024-03-15 10:00:00';"

# Switch application to recovery instance after verification
# Update Secrets Manager with new endpoint
```

### Audit Log Chain Recovery
The audit log uses a hash chain. If a break is detected:
1. DO NOT delete any records (potential evidence)
2. Extract the chain break point from `verify_chain` output
3. Escalate to CTO and legal (potential tampering or bug)
4. Preserve all CloudWatch logs for forensics
5. Engage external forensics firm if tampering is suspected
