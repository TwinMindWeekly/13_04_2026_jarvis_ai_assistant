import { defineConfig, devices } from '@playwright/test'

/**
 * Playwright config for JARVIS frontend E2E tests.
 *
 * Tests assume:
 *   - Frontend dev server running on http://localhost:5173 (started automatically below)
 *   - Backend running on http://localhost:8000 — start manually before `npm run test:e2e`
 *     (we don't auto-start backend because it requires Python venv + .env keys).
 */
export default defineConfig({
  testDir: './e2e',
  timeout: 30_000,
  expect: { timeout: 5_000 },
  fullyParallel: false, // run sequentially — single backend instance
  workers: 1,
  reporter: [['list'], ['html', { open: 'never' }]],
  use: {
    baseURL: 'http://localhost:5173',
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
  },
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],
  webServer: {
    command: 'npm run dev',
    url: 'http://localhost:5173',
    reuseExistingServer: true,
    timeout: 60_000,
  },
})
