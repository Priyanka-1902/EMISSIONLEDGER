# ADR-001: Multi-Tenant Isolation via PostgreSQL Row-Level Security

**Status:** Accepted  
**Date:** 2024-01-15  
**Deciders:** CTO, Lead Architect, Head of Security

## Context

EmissionLedger will serve 20 pilot SMEs in Phase 1, growing to 200+ in commercial launch.
Each tenant's emissions data, financial CBAM exposure figures, and audit logs are commercially
sensitive and regulatorily significant. A data isolation breach between tenants would:
- Expose competitor emission data (commercial harm)
- Compromise CBAM disclosure integrity (regulatory violation)
- Trigger DPDP Act 2023 breach notification obligations
- Destroy the trust required for the platform to operate

We must choose an isolation architecture that scales, is auditable, and provably correct.

## Options Considered

### Option A: Separate Database Per Tenant
- Full isolation; no shared resources
- **Rejected:** Operational complexity unbounded with 200+ tenants; migration burden; cost

### Option B: Separate Schema Per Tenant
- Good isolation; single database cluster
- **Rejected:** Schema proliferation creates migration complexity; TimescaleDB hypertables
  don't support per-schema continuous aggregates efficiently

### Option C: Shared Schema + tenant_id Column + Row-Level Security (RLS)
- Single schema; tenant isolation enforced by PostgreSQL at the kernel level
- RLS policy: `USING (tenant_id = current_setting('app.current_tenant_id')::uuid)`
- Application sets `SET LOCAL app.current_tenant_id = '{tenant_id}'` at session start
- **Accepted**

### Option D: Application-Level Filtering
- Add `WHERE tenant_id = ?` to every query
- **Rejected:** Single missed WHERE clause causes data breach; not auditable; developer error surface too large

## Decision

Use **PostgreSQL Row-Level Security (Option C)** with:
1. `tenant_id UUID NOT NULL` on every tenant-scoped table
2. `ENABLE ROW LEVEL SECURITY` + `FORCE ROW LEVEL SECURITY` on all such tables
3. RLS policy using `current_setting('app.current_tenant_id')` (set per-request via `SET LOCAL`)
4. Application database role (`emissionledger_app`) subject to RLS; only service superuser bypasses it
5. Verified by quarterly red-team exercise (attempt cross-tenant reads with valid JWT)

## Consequences

**Positive:**
- Defense-in-depth: even if application bug omits WHERE clause, DB rejects the query
- Auditable: RLS policies are schema-level objects visible in pg_catalog
- Performant: `tenant_id` indexed on all tables; RLS adds no query planning overhead

**Negative:**
- `SET LOCAL app.current_tenant_id` must be called before any query; missed in tests → silent pass
- Alembic migrations must be run as superuser (bypasses RLS), requires care
- Continuous aggregate views require explicit policy management

## Mitigation

- Middleware enforces `set_tenant_context()` before every request handler
- Integration tests run as `emissionledger_app` role (not superuser) to exercise RLS
- CI job verifies cross-tenant isolation on every PR touching DB queries
