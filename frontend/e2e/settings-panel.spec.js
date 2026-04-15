import { test, expect } from '@playwright/test'

/**
 * Settings panel: open from sidebar, see provider/model fields, close.
 * Does NOT require backend (provider list call fails silently).
 */
test('settings panel opens and shows provider/model controls', async ({ page }) => {
  await page.goto('/')

  // Click the Settings button in sidebar (icon button or text — try both)
  const settingsBtn = page
    .getByRole('button', { name: /settings|cài đặt/i })
    .first()
  await settingsBtn.click()

  // Modal/dialog appears
  await expect(page.getByText(/provider|nhà cung cấp/i).first()).toBeVisible()

  // Model field visible
  await expect(page.getByText(/model|mô hình/i).first()).toBeVisible()

  // Close via Escape (react-bootstrap modal supports this)
  await page.keyboard.press('Escape')
  await expect(page.getByText(/provider|nhà cung cấp/i).first()).toBeHidden({
    timeout: 3000,
  })
})
