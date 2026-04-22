import { expect, test } from '@playwright/test'

import { PLAYWRIGHT_API_BASE } from './ports'

test.beforeEach(async ({ request }) => {
  await request.post(`${PLAYWRIGHT_API_BASE}/__e2e__/reset-posts`, {
    failOnStatusCode: false,
  })
})

const tinyPng = Buffer.from(
  'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhCsvLIAAAAAASUVORK5CYII=',
  'base64',
)

test.describe('posts UI', () => {
  test.describe.configure({ mode: 'serial' })

  test('shows empty state when API has no posts', async ({ page }) => {
    await page.goto('/')
    await expect(page.getByTestId('post-new-open')).toBeVisible()
    await expect(page.getByTestId('posts-empty')).toBeVisible()
    await expect(page.getByTestId('posts-table')).toHaveCount(0)
  })

  test('lists a post after seeding via API', async ({ page, request }) => {
    const name = `e2e-ui-${Date.now()}`
    const res = await request.post(`${PLAYWRIGHT_API_BASE}/posts`, {
      data: { name },
      headers: { 'Content-Type': 'application/json' },
    })
    if (!res.ok()) {
      throw new Error(`seed POST failed: ${res.status()} ${await res.text()}`)
    }

    await page.goto('/')
    await expect(page.getByTestId('posts-table')).toBeVisible()
    const row = page.getByTestId('post-row').filter({ hasText: name })
    await expect(row).toHaveCount(1)
    await expect(row.getByTestId('post-name')).toHaveText(name)
    await expect(row.getByTestId('post-created')).not.toHaveText('')
    await expect(row.getByTestId('post-status')).toContainText('Active')
  })

  test('creates a post from the new-post dialog with image (503 without GCS)', async ({
    page,
  }) => {
    const name = `ui-create-${Date.now()}`
    await page.goto('/')
    await page.getByTestId('post-new-open').click()
    await page.getByTestId('post-create-description').fill(name)
    await page.getByTestId('post-create-image').setInputFiles({
      name: '1x1.png',
      mimeType: 'image/png',
      buffer: tinyPng,
    })
    await page.getByTestId('post-create-submit').click()
    await expect(page.getByTestId('posts-action-error')).toContainText(
      /image uploads not configured/,
    )
  })

  test('updates a post from the row', async ({ page, request }) => {
    const oldName = `ui-before-${Date.now()}`
    const newName = `ui-after-${Date.now()}`
    const seed = await request.post(`${PLAYWRIGHT_API_BASE}/posts`, {
      data: { name: oldName },
      headers: { 'Content-Type': 'application/json' },
    })
    if (!seed.ok()) {
      throw new Error(`seed failed: ${seed.status()}`)
    }
    await page.goto('/')
    const row = page.getByTestId('post-row').filter({ hasText: oldName })
    await expect(row).toHaveCount(1)
    const postId = await row.getAttribute('data-post-id')
    if (!postId) {
      throw new Error('expected data-post-id on post row')
    }
    const rowById = page.locator(
      `[data-testid="post-row"][data-post-id="${postId}"]`,
    )

    await rowById.getByTestId('post-edit').click()
    await rowById.getByTestId('post-edit-name').fill(newName)
    await rowById.getByTestId('post-edit-save').click()

    await expect(
      page.getByTestId('post-row').filter({ hasText: newName }),
    ).toHaveCount(1)
    await expect(
      page.getByTestId('post-row').filter({ hasText: oldName }),
    ).toHaveCount(0)
  })

  test('expands a post to show images and listings (read-only)', async ({
    page,
    request,
  }) => {
    const name = `ui-panel-${Date.now()}`
    const seed = await request.post(`${PLAYWRIGHT_API_BASE}/posts`, {
      data: { name },
      headers: { 'Content-Type': 'application/json' },
    })
    if (!seed.ok()) {
      throw new Error(`seed failed: ${seed.status()}`)
    }
    await page.goto('/')
    const row = page.getByTestId('post-row').filter({ hasText: name })
    await expect(row.getByTestId('post-listing-count')).toHaveText('0')

    const postId = await row.getAttribute('data-post-id')
    if (!postId) {
      throw new Error('expected data-post-id on post row')
    }
    await row.getByTestId('post-toggle-listings').click()
    const panel = page
      .locator(`[data-testid="post-listings-row"][data-post-id="${postId}"]`)
      .getByTestId('post-listings-panel')
    await expect(panel.getByTestId('post-listings-empty')).toBeVisible()
    await expect(panel.getByTestId('post-images-empty')).toBeVisible()
  })
})
