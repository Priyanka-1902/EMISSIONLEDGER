# SOC 2 Type II Control Mapping

**Framework:** AICPA Trust Services Criteria 2017  
**Target audit period:** 12 months from pilot launch  
**Auditor:** To be engaged by Month 10

## CC1 — Control Environment

| Control ID | Criteria | Control | Owner Service | Evidence |
|---|---|---|---|---|
| CC1.1 | COSO Principle 1 | Security & Acceptable Use Policy published and signed by all staff | Org | Signed policy docs in HRIS |
| CC1.2 | COSO Principle 2 | Board-approved Information Security charter | Org | Board minutes |
| CC1.3 | COSO Principle 3 | Security awareness training (annual) | Org | Training completion records |
| CC1.4 | COSO Principle 4 | Code of conduct with whistleblower channel | Org | Signed acknowledgements |
| CC1.5 | COSO Principle 5 | Performance reviews include security KPIs | Org | HR records |

## CC2 — Communication and Information

| Control ID | Criteria | Control | Owner Service | Evidence |
|---|---|---|---|---|
| CC2.1 | Relevant information identified | All security incidents logged in incident tracker | audit | Audit log exports |
| CC2.2 | Internal communication | Weekly security standup; monthly board report | Org | Meeting minutes |
| CC2.3 | External communication | Security contact page; responsible disclosure policy | Org | Website |

## CC3 — Risk Assessment

| Control ID | Criteria | Control | Owner Service | Evidence |
|---|---|---|---|---|
| CC3.1 | Risk identification | Annual risk assessment documented | Org | Risk register |
| CC3.2 | Risk analysis | CVSS-scored vulnerability tracking | Snyk/Semgrep | CI scan reports |
| CC3.3 | Risk response | Critical vulns patched within 24h; high within 7 days | All services | Snyk dashboard |

## CC4 — Monitoring

| Control ID | Criteria | Control | Owner Service | Evidence |
|---|---|---|---|---|
| CC4.1 | Monitoring activities | OpenTelemetry metrics → Grafana Cloud; alerts → PagerDuty | All services | Grafana dashboards |
| CC4.2 | Evaluation of deficiencies | Monthly security review; quarterly penetration test | Org | Pentest reports |

## CC5 — Control Activities

| Control ID | Criteria | Control | Owner Service | Evidence |
|---|---|---|---|---|
| CC5.1 | Control selection | Controls mapped to risks in risk register | Org | Risk register |
| CC5.2 | Technology controls | Automated SAST (Semgrep) + DAST (ZAP) in CI | CI/CD | GitHub Actions logs |
| CC5.3 | Policy deployment | Infrastructure-as-Code (Terraform); no manual changes | infra | Terraform state |

## CC6 — Logical and Physical Access

| Control ID | Criteria | Control | Owner Service | Evidence |
|---|---|---|---|---|
| CC6.1 | Logical access | AWS Cognito + MFA required for admin roles | auth | Cognito user pool config |
| CC6.2 | Access provisioning | Role-based access control; org_admin provisions users | auth | User creation audit logs |
| CC6.3 | Access reviews | Quarterly access review; dormant accounts disabled | auth | User audit reports |
| CC6.4 | Access revocation | Cognito account disable + active session invalidation on offboarding | auth | Offboarding runbook |
| CC6.5 | Physical access | AWS handles physical security (ISO 27001 compliant Mumbai DC) | AWS | AWS compliance reports |
| CC6.6 | Logical access to infrastructure | Only GH Actions OIDC role can push to EKS; no direct kubectl | eks | IAM policy evidence |
| CC6.7 | Transmission encryption | TLS 1.3 enforced on all endpoints; ALB policy rejects older | networking | ALB listener config |
| CC6.8 | Encryption at rest | KMS AES-256 on RDS, S3, ElastiCache, EKS secrets | kms | KMS key policies |

## CC7 — System Operations

| Control ID | Criteria | Control | Owner Service | Evidence |
|---|---|---|---|---|
| CC7.1 | System configurations | Terraform manages all infra; drift alerts via AWS Config | infra | AWS Config rules |
| CC7.2 | Vulnerability management | Snyk continuous scanning; ECR image scanning | CI/CD | Snyk reports |
| CC7.3 | Change management | Branch protection; PR review required; CI must pass | CI/CD | GitHub branch protection |
| CC7.4 | Malicious software | ECR image scanning; Kubernetes admission controller | eks | Scan reports |
| CC7.5 | Capacity management | EKS auto-scaling; RDS storage auto-scaling; CloudWatch alarms | eks, rds | CloudWatch dashboards |

## CC8 — Change Management

| Control ID | Criteria | Control | Owner Service | Evidence |
|---|---|---|---|---|
| CC8.1 | Change authorisation | All changes via PR; min 1 approver; CI gate | CI/CD | GitHub PR audit trail |

## CC9 — Risk Mitigation

| Control ID | Criteria | Control | Owner Service | Evidence |
|---|---|---|---|---|
| CC9.1 | Risk mitigation | Vendor security review for all third-party integrations | Org | Vendor assessments |
| CC9.2 | Business disruption | Multi-AZ RDS; EKS cross-AZ nodes; Redis replica | rds, eks | Architecture docs |

## A1 — Availability

| Control ID | Criteria | Control | Owner | Evidence |
|---|---|---|---|---|
| A1.1 | Availability commitments | 99.5% SLO during pilot; Uptime monitored via CloudWatch | All | Uptime reports |
| A1.2 | Capacity planning | k6 load tests at 200 concurrent users quarterly | CI/CD | Load test reports |
| A1.3 | Recovery testing | Monthly RDS restore test; DR runbook executed quarterly | Org | Restore test records |

## C1 — Confidentiality

| Control ID | Criteria | Control | Owner | Evidence |
|---|---|---|---|---|
| C1.1 | Confidential information identified | Data classification: Public / Internal / Confidential / Restricted | Org | Data classification policy |
| C1.2 | Confidential info protected | PostgreSQL RLS; tenant KMS keys; S3 bucket policies | auth, kms, s3 | Evidence per service |

## P1-P8 — Privacy (DPDP Act 2023)

| Control ID | Criteria | Control | Owner | Evidence |
|---|---|---|---|---|
| P1 | Consent | Explicit consent collected at onboarding; consent log | auth | Consent database |
| P2 | Notice | Privacy notice at registration; data processing inventory | Org | Privacy policy |
| P3 | Choice / opt-out | Right-to-erasure workflow (within 30 days) | auth | Erasure request log |
| P4 | Collection limitation | PII minimisation: only GSTIN, email, name collected | All | DPI inventory |
| P5 | Use limitation | Data used only for declared purpose (GHG accounting) | All | Purpose log |
| P6 | Security | AES-256 at rest; TLS 1.3 in transit | kms, networking | Config evidence |
| P7 | Quality | Data correction workflow for users | auth | Support tickets |
| P8 | Monitoring | Annual privacy impact assessment | Org | PIA document |
