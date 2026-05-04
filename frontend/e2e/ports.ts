/** Ports for Playwright. Override with env vars to run against real dev servers:
 *   PLAYWRIGHT_API_BASE=http://localhost:8000 PLAYWRIGHT_WEB_PORT=5173 npx playwright test ...
 */
export const PLAYWRIGHT_API_PORT = Number(process.env.PLAYWRIGHT_API_PORT ?? 9876)
export const PLAYWRIGHT_WEB_PORT = Number(process.env.PLAYWRIGHT_WEB_PORT ?? 5174)
export const PLAYWRIGHT_API_BASE =
  process.env.PLAYWRIGHT_API_BASE ?? `http://127.0.0.1:${PLAYWRIGHT_API_PORT}`
