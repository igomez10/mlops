/** Ports for Playwright so local dev servers on 8000 / 5173 are not blocked. */
export const PLAYWRIGHT_API_PORT = 9876
export const PLAYWRIGHT_WEB_PORT = 5174
export const PLAYWRIGHT_API_BASE = `http://127.0.0.1:${PLAYWRIGHT_API_PORT}`
