import { expect, test } from '@playwright/test'

import { PLAYWRIGHT_API_BASE } from './ports'

test.describe('posts UI', () => {
  test.describe.configure({ mode: 'serial' })

  test('shows empty state when API has no posts', async ({ page }) => {
    await page.goto('/')
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
})
