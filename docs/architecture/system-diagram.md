# EmissionLedger System Architecture

## Component Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  CLIENT LAYER                                                                │
│                                                                              │
│  ┌──────────────────────┐  ┌─────────────────┐  ┌───────────────────────┐  │
│  │  Web App (React 18)  │  │  Mobile PWA      │  │  API Consumers        │  │
│  │  app.emissionledger  │  │  (offline entry) │  │  (Zoho/SAP webhooks)  │  │
│  └──────────┬───────────┘  └────────┬────────┘  └──────────┬────────────┘  │
└─────────────┼────────────────────────┼─────────────────────┼───────────────┘
              │ HTTPS / TLS 1.3        │                      │
┌─────────────▼────────────────────────▼──────────────────────▼───────────────┐
│  EDGE / SECURITY LAYER (AWS ap-south-1)                                      │
│                                                                              │
│  ┌─────────────┐  ┌──────────────────┐  ┌──────────────────────────────┐   │
│  │  CloudFront │  │  AWS WAF + Shield │  │  AWS Cognito (Auth/MFA/SSO)  │   │
│  │  (CDN/SPA)  │  │  Geo-restriction  │  │  JWKS endpoint               │   │
│  └──────┬──────┘  └────────┬─────────┘  └──────────────────────────────┘   │
│         │                  │                                                  │
│  ┌──────▼──────────────────▼──────────────────────────────────────────────┐ │
│  │  Application Load Balancer (HTTPS, ACM cert, access logs to S3)        │ │
│  └──────────────────────────────┬─────────────────────────────────────────┘ │
└─────────────────────────────────┼────────────────────────────────────────────┘
                                  │
┌─────────────────────────────────▼────────────────────────────────────────────┐
│  MICROSERVICES LAYER (AWS EKS — Kubernetes 1.29, Bottlerocket nodes)         │
│                                                                              │
│  ┌─────────────┐  ┌──────────────┐  ┌────────────────┐  ┌───────────────┐  │
│  │   Auth SVC  │  │  Calculation │  │  Ingestion SVC │  │  Reporting    │  │
│  │   :8001     │  │  Engine :8003│  │  :8002         │  │  SVC :8004    │  │
│  │  • JWT/RBAC │  │  • GHG math  │  │  • Tally TDL  │  │  • CBAM XML   │  │
│  │  • Cognito  │  │  • CBAM calc │  │  • Zoho API   │  │  • GHG PDF    │  │
│  │  • Sessions │  │  • Factor lib│  │  • SAP B1     │  │  • BRSR       │  │
│  └─────────────┘  └──────────────┘  │  • CSV/OCR    │  │  • BEE/PAT    │  │
│                                      └────────────────┘  └───────────────┘  │
│  ┌─────────────┐  ┌──────────────┐  ┌────────────────────────────────────┐  │
│  │  Audit SVC  │  │Notification  │  │  Rules Engine (sidecar)             │  │
│  │  :8005      │  │  SVC :8006   │  │  • CBAM rules (versioned JSON)      │  │
│  │  • Hash chain│  │  • Email/SMS │  │  • BEE/PAT rules                   │  │
│  │  • Tamper-EV│  │  • Webhooks  │  │  • Auto-update from pub. feeds      │  │
│  └─────────────┘  └──────────────┘  └────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────────────────┘
                          │
┌─────────────────────────▼────────────────────────────────────────────────────┐
│  DATA LAYER (AWS ap-south-1, all encrypted at rest with KMS)                 │
│                                                                              │
│  ┌─────────────────────────────────┐  ┌──────────────────────────────────┐  │
│  │  RDS PostgreSQL 15 (Multi-AZ)   │  │  ElastiCache Redis 7 (cluster)   │  │
│  │  + TimescaleDB extension        │  │  • JWT session store              │  │
│  │  • Row-Level Security (RLS)     │  │  • Rate limiting                  │  │
│  │  • Tenant isolation via         │  │  • Report generation queue        │  │
│  │    app.current_tenant_id        │  │  • API response cache             │  │
│  │  • emission_records hypertable  │  └──────────────────────────────────┘  │
│  │  • Continuous aggregates        │                                         │
│  │  • 7-year audit log retention   │  ┌──────────────────────────────────┐  │
│  └─────────────────────────────────┘  │  S3 (Object Lock + Versioning)   │  │
│                                        │  • documents/ (raw uploads)       │  │
│  ┌─────────────────────────────────┐  │  • reports/ (10yr COMPLIANCE)     │  │
│  │  AWS Secrets Manager            │  │  • factors/ (GHG factor YAMLs)    │  │
│  │  • Per-tenant Zoho/Tally creds  │  │  • ml-models/ (SageMaker artefacts│  │
│  │  • DB passwords                 │  └──────────────────────────────────┘  │
│  │  • API keys                     │                                         │
│  └─────────────────────────────────┘                                         │
└──────────────────────────────────────────────────────────────────────────────┘
                          │
┌─────────────────────────▼────────────────────────────────────────────────────┐
│  ML / AI LAYER                                                               │
│                                                                              │
│  ┌──────────────────────┐  ┌────────────────────────────────────────────┐   │
│  │  SageMaker Endpoints │  │  MLflow (model registry + experiment track)│   │
│  │  • xlm-roberta-base  │  │  • A/B testing                             │   │
│  │    (invoice classify)│  │  • Drift detection (monthly)               │   │
│  │  • XGB+LGBM stacked  │  │  • Model versioning                        │   │
│  │    (Scope 3 estimate)│  └────────────────────────────────────────────┘   │
│  └──────────────────────┘                                                    │
└──────────────────────────────────────────────────────────────────────────────┘
                          │
┌─────────────────────────▼────────────────────────────────────────────────────┐
│  EXTERNAL INTEGRATIONS                                                       │
│                                                                              │
│  ┌──────────────┐  ┌──────────────┐  ┌────────────────┐  ┌───────────────┐ │
│  │  Tally Prime │  │  Zoho Books  │  │  DISCOM portals│  │  EU CBAM      │ │
│  │  (TDL/XML    │  │  (OAuth API) │  │  BESCOM/MSEDCL │  │  Registry API │ │
│  │   port 9000) │  │              │  │  TNEB/TSECPDCL │  │               │ │
│  └──────────────┘  └──────────────┘  └────────────────┘  └───────────────┘ │
│                                                                              │
│  ┌──────────────┐  ┌──────────────┐  ┌────────────────┐                    │
│  │  SAP B1      │  │  Delhivery / │  │  CEA / BEE /   │                    │
│  │  Service     │  │  Shiprocket  │  │  MoEFCC feeds  │                    │
│  │  Layer REST  │  │  (logistics) │  │  (rule updates)│                    │
│  └──────────────┘  └──────────────┘  └────────────────┘                    │
└──────────────────────────────────────────────────────────────────────────────┘
```

## Security Boundaries

| Boundary | Control |
|---|---|
| Internet → Edge | CloudFront + WAF geo-restriction + Shield Standard |
| Edge → Services | ALB with HTTPS only; security groups restrict source |
| Services → DB | PostgreSQL RLS + VPC security groups (no public access) |
| Service ↔ Service | mTLS via Istio service mesh; JWT propagation |
| Secrets | AWS Secrets Manager; never in environment variables or code |
| Encryption at rest | AES-256 via AWS KMS; per-service dedicated keys |
| Encryption in transit | TLS 1.3 minimum |
| Tenant isolation | PostgreSQL RLS + `SET LOCAL app.current_tenant_id` per request |

## Data Flow — CBAM Report Generation

```
SME Data Entry / Tally/Zoho Sync
      │
      ▼
Ingestion Service → classifies activities → validation queue
      │                                            │
      ▼                                    Human review (low-confidence)
Calculation Engine
  • loads emission factors (CEA / CBAM defaults)
  • computes tCO2e with uncertainty bounds
  • writes EmissionRecord with input_hash + output_hash
      │
      ▼
Reporting Service
  • aggregates by CN code / goods category
  • CBAMCalculator.calculate_line() → applies 3x default multiplier
  • generate_cbam_xml() → validated CBAM-TR-XML
  • cryptographic signature → embedded QR audit trail
      │
      ▼
Verifier Workflow (EU-accredited verifier portal)
      │
      ▼
EU CBAM Registry submission (XML + verifier sign-off)
      │
      ▼
Audit Service: every step hash-chained to immutable ledger
```
