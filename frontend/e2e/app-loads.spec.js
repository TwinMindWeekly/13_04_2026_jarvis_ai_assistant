import { test, expect } from '@playwright/test'

/**
 * Smoke test: the app loads, sidebar renders, empty state shows the prompt input.
 * Does NOT require backend to be running — pure frontend render test.
 */
test('app loads with sidebar and empty state input', async ({ page }) => {
  await page.goto('/')

  // App title visible in header
  await expect(page.getByRole('button', { name: /JARVIS/i }).first()).toBeVisible()

  // Empty state input visible (chat is empty by default)
  const input = page.locator('textarea, input[type="text"]').first()
  await expect(input).toBeVisible()

  // No assistant messages yet
  const messages = page.locator('[data-message-role="assistant"]')
  await expect(messages).toHaveCount(0)
})
