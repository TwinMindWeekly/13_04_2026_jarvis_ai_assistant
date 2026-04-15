import { test, expect } from '@playwright/test'

/**
 * Documents panel: open via sidebar Documents button, see upload affordance.
 * Does NOT require backend (list fetch may fail silently — UI still renders).
 */
test('documents panel opens with upload control', async ({ page }) => {
  await page.goto('/')

  // Click Documents button in sidebar (icon or text)
  const docsBtn = page
    .getByRole('button', { name: /documents|tài liệu/i })
    .first()
  await docsBtn.click()

  // Modal appears with upload affordance (file input or upload label)
  const uploadAffordance = page
    .locator('input[type="file"], label:has-text(/upload|tải lên/i)')
    .first()
  await expect(uploadAffordance).toBeAttached({ timeout: 5000 })

  // Close via Escape
  await page.keyboard.press('Escape')
})
