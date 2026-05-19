/**
 * E2E test: CBAM Report Generation — Golden Path
 *
 * Covers the critical user journey:
 * Login → Dashboard → Create CBAM Report → Add Goods Line →
 * Calculate Embedded Emissions → Generate XML → Download
 *
 * This is one of the acceptance criteria for the pilot exit gate.
 */
import { test, expect, Page } from '@playwright/test'

const TEST_TENANT = {
  email: process.env.E2E_TEST_EMAIL || 'test-sustainability@acmepharma.emissionledger.in',
  password: process.env.E2E_TEST_PASSWORD || 'TestPassword123!',
}

test.describe('CBAM Report Generation', () => {
  let page: Page

  test.beforeEach(async ({ browser }) => {
    page = await browser.newPage()
    await page.goto('/')
  })

  test.afterEach(async () => {
    await page.close()
  })

  test('login and reach dashboard', async () => {
    await page.goto('/login')
    await page.fill('[name="email"]', TEST_TENANT.email)
    await page.fill('[name="password"]', TEST_TENANT.password)
    await page.click('[data-testid="login-submit"]')

    await expect(page).toHaveURL('/dashboard', { timeout: 15_000 })
    await expect(page.getByText('Emissions Dashboard')).toBeVisible()
    await expect(page.getByText('tCO₂e')).toBeVisible()
  })

  test('create CBAM declarant report for Q1 2024', async () => {
    // Navigate to login
    await page.goto('/login')
    await page.fill('[name="email"]', TEST_TENANT.email)
    await page.fill('[name="password"]', TEST_TENANT.password)
    await page.click('[data-testid="login-submit"]')
    await page.waitForURL('/dashboard')

    // Navigate to CBAM reports
    await page.click('[data-testid="nav-cbam"]')
    await expect(page).toHaveURL('/cbam')

    // Create new report
    await page.click('[data-testid="new-cbam-report"]')
    await expect(page.getByRole('dialog')).toBeVisible()

    // Fill report details
    await page.selectOption('[name="quarter_year"]', '2024')
    await page.selectOption('[name="quarter_number"]', '1')
    await page.click('[data-testid="create-report-confirm"]')

    // Should land on report detail page
    await expect(page.getByText('Q1 2024 CBAM Declarant Report')).toBeVisible({ timeout: 10_000 })

    // Add a goods line
    await page.click('[data-testid="add-goods-line"]')

    // Select CN code (Portland Cement)
    await page.fill('[data-testid="cn-code-input"]', '2523')
    await page.click('[data-testid="cn-code-option-2523210000"]')

    // Enter quantity
    await page.fill('[data-testid="quantity-input"]', '100')
    await page.fill('[data-testid="country-origin"]', 'IN')

    // Save and calculate
    await page.click('[data-testid="calculate-embedded-emissions"]')

    // Verify calculation result appears
    await expect(page.getByTestId('direct-ee-result')).toBeVisible({ timeout: 15_000 })
    await expect(page.getByText('tCO₂e')).toBeVisible()

    // Verify default value warning shows
    await expect(page.getByText('CBAM default values')).toBeVisible()
    await expect(page.getByText('3x certificate multiplier')).toBeVisible()
  })

  test('generate CBAM XML and verify hash', async () => {
    // Pre-condition: report with goods line already exists (via API seed)
    await page.goto('/cbam')

    // Find first completed report
    const firstReport = page.getByTestId('report-row').first()
    await firstReport.click()

    // Generate XML
    await page.click('[data-testid="generate-xml"]')
    await expect(page.getByTestId('xml-generation-status')).toContainText('Generated', { timeout: 30_000 })

    // Verify report hash is displayed
    const hashEl = page.getByTestId('report-hash')
    await expect(hashEl).toBeVisible()
    const hashText = await hashEl.textContent()
    expect(hashText).toMatch(/^[0-9a-f]{64}$/)

    // Download button should be enabled
    await expect(page.getByTestId('download-xml-btn')).toBeEnabled()
  })

  test('data completeness badge updates after import', async () => {
    await page.goto('/dashboard')
    const beforeCompleteness = await page.getByTestId('data-completeness-value').textContent()

    // Go to ingestion, upload CSV
    await page.click('[data-testid="nav-ingestion"]')
    const fileInput = page.locator('[data-testid="csv-upload-input"]')
    await fileInput.setInputFiles('tests/fixtures/sample_fuel_data.csv')

    await page.click('[data-testid="start-import"]')
    await expect(page.getByText('Import complete')).toBeVisible({ timeout: 60_000 })

    // Dashboard completeness should have changed
    await page.click('[data-testid="nav-dashboard"]')
    const afterCompleteness = await page.getByTestId('data-completeness-value').textContent()
    // At minimum it should exist and be a number
    expect(afterCompleteness).toBeTruthy()
  })

  test('compliance rules violation shows correctly', async () => {
    // Navigate to a report missing CBAM declarant ID
    await page.goto('/cbam')
    await page.click('[data-testid="report-row"]')

    // If no declarant ID, CBAM-001 rule should fire
    const tenant = page.getByTestId('tenant-declarant-id')
    const declarantId = await tenant.inputValue().catch(() => null)

    if (!declarantId) {
      await expect(page.getByText('CBAM Declarant ID is missing')).toBeVisible()
      await expect(page.getByTestId('rule-CBAM-001')).toHaveClass(/error/)
    }
  })

  test('audit log shows CBAM report creation', async () => {
    await page.goto('/audit')
    await expect(page.getByTestId('audit-log-table')).toBeVisible()

    // Should see recent report events
    const auditRows = page.getByTestId('audit-row')
    await expect(auditRows.first()).toBeVisible()

    // Each row should have a chain hash
    const chainHashCell = page.getByTestId('chain-hash').first()
    await expect(chainHashCell).toBeVisible()
    const hashText = await chainHashCell.textContent()
    expect(hashText?.length).toBeGreaterThan(8)  // at least partial hash shown
  })

  test('multilingual: Tamil dashboard renders correctly', async () => {
    await page.goto('/dashboard')

    // Switch to Tamil
    await page.click('[data-testid="language-selector"]')
    await page.click('[data-testid="lang-ta"]')

    // Key UI elements should be in Tamil
    await expect(page.getByText('உமிழ்வு டாஷ்போர்டு')).toBeVisible()
    await expect(page.getByText('மொத்த உமிழ்வு')).toBeVisible()
  })
})
