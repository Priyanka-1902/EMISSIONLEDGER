# ADR-002: TimescaleDB Hypertable for Emission Records

**Status:** Accepted  
**Date:** 2024-01-15

## Context

Emission records are fundamentally time-series data. A typical SME will generate:
- ~10,000 records/year (fuel + electricity bills, Tally vouchers)
- 3-year historical backfill at pilot launch → 30,000 initial records per tenant
- 20 tenants × 30,000 = 600,000 records at pilot start; 200 tenants → 6M records

Key access patterns:
1. Monthly aggregations for dashboards (heavy read)
2. Range queries for report period (e.g., Q3 2024 April–June)
3. Drill-down to individual records (by tenant + date range + scope)
4. Historical backfill inserts (bulk write)

## Decision

Use **TimescaleDB hypertable** on `emission_records`, partitioned by `activity_date` monthly:

```sql
SELECT create_hypertable('emission_records', 'activity_date',
  chunk_time_interval => INTERVAL '1 month');
```

With **continuous aggregates** for monthly totals:
```sql
CREATE MATERIALIZED VIEW emission_monthly_totals
WITH (timescaledb.continuous) AS ...
```

## Rationale

- TimescaleDB is a PostgreSQL extension — zero new operational surface
- Monthly chunks mean old data is automatically compressed (TimescaleDB compression policy)
- Continuous aggregates pre-compute monthly totals; dashboard load time < 200ms even at 100M records
- `time_bucket` functions enable natural quarterly aggregations for CBAM reports
- Compatible with RLS (policies apply to underlying hypertable)

## Performance Targets

| Query | Target P95 | Mechanism |
|---|---|---|
| Dashboard summary (current year) | < 200ms | Continuous aggregate |
| Report period range query | < 500ms | Hypertable chunk pruning + index |
| Bulk backfill (10k records) | < 5s | Batch insert via COPY |
| Drill-down to single record | < 50ms | UUID primary key lookup |
