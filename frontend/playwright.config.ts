import { defineConfig, devices } from '@playwright/test'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

import {
  PLAYWRIGHT_API_BASE,
  PLAYWRIGHT_API_PORT,
  PLAYWRIGHT_WEB_PORT,
} from './e2e/ports'

const frontendRoot = path.dirname(fileURLToPath(import.meta.url))
const repoRoot = path.join(frontendRoot, '..')
const backendPython = path.join(repoRoot, '.venv', 'bin', 'python')

export default defineConfig({
  testDir: 'e2e',
  fullyParallel: false,
  workers: 1,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  reporter: 'list',
  use: {
    ...devices['Desktop Chrome'],
    baseURL: `http://127.0.0.1:${PLAYWRIGHT_WEB_PORT}`,
    trace: 'on-first-retry',
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
  webServer: [
    {
      command: `${backendPython} -m uvicorn server:app --host 127.0.0.1 --port ${PLAYWRIGHT_API_PORT}`,
      cwd: repoRoot,
      env: {
        ...process.env,
        PYTHONPATH: repoRoot,
        MONGODB_URI: '',
        E2E_TEST: '1',
      },
      url: `${PLAYWRIGHT_API_BASE}/health`,
      reuseExistingServer: !process.env.CI,
      timeout: 120_000,
    },
    {
      command: `npm run dev -- --host 127.0.0.1 --port ${PLAYWRIGHT_WEB_PORT}`,
      cwd: frontendRoot,
      env: {
        ...process.env,
        VITE_API_BASE_URL: PLAYWRIGHT_API_BASE,
      },
      url: `http://127.0.0.1:${PLAYWRIGHT_WEB_PORT}`,
      reuseExistingServer: !process.env.CI,
      timeout: 120_000,
    },
  ],
})
