# SME Tenant Onboarding Runbook

**Target:** < 15 minutes time-to-first-report (automated)  
**Goal for pilot:** ≥ 80% complete onboarding without human assistance

## Pre-Onboarding Checklist (Internal, before partner receives invite)

- [ ] KYC verified: GSTIN valid, PAN matches MCA database
- [ ] CBAM eligibility assessed: does the SME export to EU?
- [ ] BEE DC status checked: is annual energy > 100 TOE?
- [ ] Tier assigned and confirmed with sales team
- [ ] Pilot partner agreement signed (data processing addendum included)
- [ ] Cognito tenant group created: `{tenant_slug}:org_admin`
- [ ] Tenant record seeded via script

## Tenant Provisioning (3 minutes, automated)

```bash
python scripts/provision_tenant.py \
  --legal-name "Tirupur Fabrics Pvt Ltd" \
  --gstin "33AABCT1234A1ZP" \
  --pan "AABCT1234A" \
  --city "Tirupur" \
  --state "TN" \
  --industry-sector "textiles" \
  --isic-code "1311" \
  --tier "growth" \
  --eu-exporter true \
  --admin-email "sustainability@tirupurfabrics.com"
```

This script:
1. Creates tenant record in PostgreSQL
2. Creates AWS KMS per-tenant key
3. Creates Cognito user + org_admin group
4. Sends welcome email with OTP
5. Sets S3 folder permissions (`documents/{tenant_id}/`, `reports/{tenant_id}/`)
6. Creates default facility (tenant's registered address)

## Self-Serve Onboarding Flow (User-facing, 12 minutes)

### Step 1: Accept Invite + Set Password + Enrol MFA (2 min)
- User clicks email link → Cognito hosted UI
- Sets strong password (12+ chars)
- Enrolls TOTP authenticator (Google Authenticator / Authy)

### Step 2: Verify Organisation Details (2 min)
- Pre-filled from GSTIN: legal name, address, PAN
- User confirms / corrects
- Adds: CBAM Declarant ID (if already registered) or starts registration

### Step 3: Add Facilities (3 min)
- Default facility pre-created from registered address
- User adds plant addresses, DISCOMs, meter numbers
- Grid region auto-detected from state

### Step 4: Connect Data Source (4 min)

**Option A — Tally Prime:**
1. User enters Tally server IP and port
2. Platform tests connectivity: `curl http://{ip}:{port}/`
3. If successful, platform starts 15-minute sync schedule

**Option B — Zoho Books:**
1. Click "Connect Zoho Books"
2. Redirect to Zoho OAuth → user authorises
3. Platform stores refresh token in Secrets Manager

**Option C — CSV Upload:**
1. Download template (fuel_consumption_template.xlsx)
2. Fill in historical data (up to 3 years)
3. Upload → validation → import

### Step 5: First Report Preview (1 min)
- After data import, platform calculates all emission records
- Shows "Preview: Your Q1 2024 emissions are X tCO₂e"
- User clicks "Generate CBAM Report" to complete onboarding

## Troubleshooting Common Issues

| Issue | Diagnosis | Resolution |
|---|---|---|
| Tally connection fails | Port 9000 not accessible | SME needs to whitelist platform IP on firewall |
| Zoho OAuth fails | Redirect URI mismatch | Check Zoho app settings; URI = `https://app.emissionledger.in/connect/zoho/callback` |
| CSV rejected | Date format | Must be YYYY-MM-DD; common issue: DD/MM/YYYY from Indian Tally exports |
| No electricity factor | DISCOM not mapped | Add DISCOM → grid_region mapping in `shared/factors/india_grid.yaml` |
| GSTIN validation fails | Test GSTIN used | Platform validates checksum; use real GSTIN or sandbox mode |

## Sandbox Mode

All pilot SMEs get access to a sandbox environment pre-loaded with synthetic data:
- 12 months of synthetic fuel + electricity records
- 3 sample CBAM goods lines
- Pre-generated sample report (read-only)

Activate: Settings → "Switch to Sandbox Mode"
