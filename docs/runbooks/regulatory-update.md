# Regulatory Update Runbook

## Trigger

Run this runbook when:
- EU DG TAXUD publishes a new CBAM Implementing Regulation or amendment
- CEA publishes a new CO2 Baseline Database version
- BEE announces new PAT cycle targets
- MoEFCC updates BRSR disclosure requirements
- IPCC publishes new GWP values (AR7)

Target: All regulatory updates applied within **5 business days** of publication.

## Step 1 — Detection

Automated ingestion pipeline (runs daily):
```bash
python services/compliance_watcher/watch_feeds.py
# Watches:
# - EUR-Lex RSS for CBAM regulations
# - CEA website for CO2 Baseline updates
# - BEE portal for PAT notifications
# - MoEFCC for BRSR updates
```

Manual check: Subscribe to EU CBAM newsletter at ec.europa.eu/taxation_customs/cbam

## Step 2 — Assessment

1. Download the new publication
2. Diff against current factor library / rules files:
   ```bash
   python scripts/diff_regulation.py \
     --current shared/factors/cbam_defaults.yaml \
     --publication downloads/new_cbam_reg.pdf
   ```
3. Document affected tenants:
   ```sql
   SELECT COUNT(DISTINCT tenant_id) as affected_tenants,
          COUNT(*) as affected_reports
   FROM reports
   WHERE status IN ('draft', 'in_review')
     AND cbam_goods_category IS NOT NULL
     AND reporting_period_end >= CURRENT_DATE - INTERVAL '1 year';
   ```

## Step 3 — Human Review (Head of Emissions Intelligence)

Before any rule takes effect:
- Review the diff with the Head of Emissions Intelligence
- Document any interpretive decisions (e.g., which methodology section applies)
- Flag for CEO review if the change affects > 30% of pilot tenants' exposure

## Step 4 — Update Factor Library / Rules

For factor updates (e.g., new CEA grid factors):
```yaml
# Add to shared/factors/india_grid.yaml:
- id: "cea-national-2024-25"
  name: "India National Grid — Combined Margin (2024-25)"
  activity_type: "purchased_electricity"
  grid_region: "national"
  value: "0.6982"           # new value
  effective_from: "2024-04-01"
  effective_to: null
  version: "19.0.0"
  # OLD factor gets effective_to set:
# - id: "cea-national-2023-24" effective_to: "2024-03-31"
```

For rule updates:
```json
// shared/rules/cbam_rules.json — increment version, add/modify rule
```

PR must include:
- The regulation citation
- Source document S3 key (`factors/source-docs/`)
- Before/after diff of affected numbers
- Impact analysis: which tenants, which reports

## Step 5 — Impact Preview

```bash
python scripts/simulate_rule_impact.py \
  --new-factor-file shared/factors/india_grid.yaml \
  --dry-run \
  --output docs/impact-previews/$(date +%Y%m%d)-cea-update.md
```

Preview is shown in the UI: "This rule change will affect 47 of your reports — re-calculate now?"

## Step 6 — Activate

After approval, merge the PR:
1. CI runs: factor library validation tests, rules engine tests
2. On merge to main: deploy triggers automated re-calculation of all affected draft reports
3. Users are notified via in-app notification + email: "Your reports have been updated with the latest emission factors"

## Step 7 — Re-Calculation Job

```bash
# Triggered automatically by deploy; can also run manually:
kubectl create job --from=cronjob/factor-recalc factor-recalc-manual-$(date +%Y%m%d) \
  -n emissionledger
```

The re-calculation job:
1. Identifies all EmissionRecord rows with `factor_version_hash` matching old factor
2. Re-calculates using new factor (creates new record version, marks old as superseded)
3. Updates all affected Report totals
4. Creates audit log entries for each change
5. Sends email digest to tenant sustainability officers

## Rollback

If an error is found after activation:
```bash
# Revert PR merge; redeploy; re-run recalculation job to restore old values
git revert $MERGE_COMMIT --no-edit
git push origin main
```

All previous factor values are preserved (immutable records); rollback only changes
which factor is the "current" one for new calculations.
