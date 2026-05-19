# EmissionLedger — Pilot-Ready Carbon Accounting Platform

Multi-tenant SaaS platform for EU CBAM, BEE/PAT, GHG Protocol, and BRSR disclosures. Deployed on AWS EKS (ap-south-1) for 20 Indian manufacturing SME pilot partners.

## Repository Layout

```
emissionledger/
├── services/
│   ├── auth/              FastAPI auth service (Cognito, JWT, RBAC)
│   ├── ingestion/         Data ingestion (Tally, Zoho, SAP, CSV, OCR)
│   ├── calculation/       GHG calculation engine (3-scope, CBAM methodology)
│   ├── reporting/         Report generator (CBAM XML, GHG PDF, BRSR, BEE/PAT)
│   ├── audit/             Hash-chained audit ledger
│   ├── notification/      Email, SMS, webhook notifications
│   └── api-gateway/       Kong/custom gateway with rate limiting
├── frontend/              React 18 + TypeScript + Vite + Tailwind
├── infra/                 Terraform (EKS, RDS, ElastiCache, S3, Cognito, KMS)
├── ml/
│   ├── invoice-classifier/ xlm-roberta-base fine-tuning pipeline
│   └── scope3-estimator/  XGBoost+LightGBM stacked ensemble
├── shared/
│   ├── schemas/           Pydantic v2 shared data models
│   ├── factors/           GHG emission factor library with provenance
│   └── rules/             Version-controlled compliance rules engine
├── migrations/            Alembic multi-tenant schema migrations
├── .github/workflows/     CI/CD with SAST, DAST, Snyk, blue-green
└── docs/
    ├── adr/               Architecture Decision Records
    ├── runbooks/          Operational runbooks
    └── soc2/              SOC 2 control mapping
```

## Quick Start (Local Dev)

```bash
cp .env.example .env          # fill in secrets
docker compose up -d          # postgres, redis, localstack
cd services/calculation && pip install -e ".[dev]" && uvicorn app.main:app --reload
cd frontend && pnpm install && pnpm dev
```

## Pilot Acceptance Gate

- 20 SMEs × ≥1 EU CBAM report accepted by EU-accredited verifier
- ≥95% emission numbers within ±5% of auditor recalculation
- Platform uptime ≥99.5% over 6-month pilot
- Zero critical findings in external penetration test
- NPS ≥40 from pilot end users
