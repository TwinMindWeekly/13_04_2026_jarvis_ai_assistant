import { test, expect } from '@playwright/test'

/**
 * Knowledge Graph panel — opens from sidebar, shows either empty state (no docs)
 * or the force-graph canvas. Does NOT require backend running: /api/graph/data
 * may fail silently; we only assert the UI shell renders.
 */
test('knowledge graph panel opens with toolbar and canvas', async ({ page }) => {
  await page.goto('/')

  // Click the Knowledge Graph button in sidebar.
  const graphBtn = page
    .getByRole('button', { name: /knowledge graph|đồ thị tri thức/i })
    .first()
  await graphBtn.click()

  // Modal title visible.
  await expect(page.getByText(/knowledge graph|đồ thị tri thức/i).first()).toBeVisible()

  // Threshold slider visible.
  await expect(page.getByText(/threshold|ngưỡng/i).first()).toBeVisible()

  // Either empty state OR a canvas element (react-force-graph renders <canvas>).
  const canvas = page.locator('canvas').first()
  const empty = page.getByText(/upload at least 2 documents|upload ít nhất 2 tài liệu/i).first()
  await expect(canvas.or(empty)).toBeVisible({ timeout: 5000 })

  // Close.
  await page.keyboard.press('Escape')
})
