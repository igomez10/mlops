/**
 * Live end-to-end test against real services.
 *
 * Skipped unless PLAYWRIGHT_LIVE_E2E=1 is set — requires real GCS, Gemini,
 * and eBay credentials plus locally running servers.
 *
 * Requires:
 *   - UI running at http://localhost:5173  (make frontend-dev)
 *   - API running at http://localhost:8000  (make dev-server)
 *   - Real GCS, Gemini/ProductAnalyzer, and eBay credentials configured in the API
 *
 * Run with:
 *   PLAYWRIGHT_LIVE_E2E=1 \
 *   PLAYWRIGHT_API_BASE=http://localhost:8000 \
 *   PLAYWRIGHT_WEB_PORT=5173 \
 *   npx playwright test e2e/posts.live.spec.ts --headed
 */
import { expect, test } from '@playwright/test'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

import { PLAYWRIGHT_API_BASE } from './ports'

const frontendDir = path.dirname(fileURLToPath(import.meta.url))
const repoRoot = path.join(frontendDir, '..', '..')
const airpodsFixturePath = path.join(repoRoot, 'fixtures', 'airpods.jpg')

test.use({
  baseURL: 'http://localhost:5173',
  // AI analysis (Gemini) + eBay category/aspect lookup can take ~30–60 s.
  actionTimeout: 90_000,
  navigationTimeout: 15_000,
})

test('uploads AirPods image and shows non-empty eBay draft (real services)', async ({
  page,
  request,
}) => {
  if (!process.env.PLAYWRIGHT_LIVE_E2E) {
    test.skip(true, 'set PLAYWRIGHT_LIVE_E2E=1 to run against real services')
  }
  test.setTimeout(120_000)
  // Best-effort cleanup — real server may not have the reset endpoint.
  await request.post(`${PLAYWRIGHT_API_BASE}/__e2e__/reset-posts`, {
    failOnStatusCode: false,
  })

  await page.goto('/')
  await page.getByTestId('post-new-open').click()

  const description = `White Apple AirPods Pro Bluetooth earbuds, good condition [${Date.now()}]`

  await page
    .getByTestId('post-create-description')
    .fill(description)

  // user_id is required for the server to build an eBay draft.
  await page.getByTestId('post-create-user-id').fill('live-e2e-test-user')

  await page.getByTestId('post-create-image').setInputFiles(airpodsFixturePath)
  await page.getByTestId('post-create-submit').click()

  // Wait for the new row to appear — AI analysis runs server-side during POST /posts.
  const row = page.getByTestId('post-row').filter({ hasText: description })
  await expect(row).toHaveCount(1, { timeout: 90_000 })

  const postId = await row.getAttribute('data-post-id')
  if (!postId) throw new Error('expected data-post-id on post row')

  await row.getByTestId('post-toggle-listings').click()

  const panel = page
    .locator(`[data-testid="post-listings-row"][data-post-id="${postId}"]`)
    .getByTestId('post-listings-panel')

  // eBay draft must be present.
  await expect(panel.getByTestId('post-ebay-draft')).toBeVisible({ timeout: 90_000 })

  // Core draft fields must be non-empty strings.
  const title = panel.getByTestId('post-ebay-draft-title')
  await expect(title).not.toHaveValue('')

  const condition = panel.getByTestId('post-ebay-draft-condition')
  await expect(condition).not.toHaveValue('')

  const price = panel.getByTestId('post-ebay-draft-price')
  await expect(price).not.toHaveValue('')

  // Product analysis should be visible.
  await expect(panel.getByTestId('post-analysis-product-name')).not.toContainText('—')
})
