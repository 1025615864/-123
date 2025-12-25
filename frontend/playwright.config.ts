import { defineConfig, devices } from '@playwright/test'

const pythonCmd = process.platform === 'win32' ? 'py' : 'python'
const backendPort = Number(process.env.E2E_BACKEND_PORT ?? 8001)
const frontendPort = Number(process.env.E2E_FRONTEND_PORT ?? 5174)
const reuseExistingBackend = !process.env.CI && process.env.E2E_REUSE_EXISTING === '1'
const reuseExistingFrontend = !process.env.CI && process.env.E2E_REUSE_EXISTING === '1'

process.env.E2E_API_BASE = process.env.E2E_API_BASE ?? `http://localhost:${frontendPort}/api`

const backendDbUrl =
  process.env.E2E_DATABASE_URL ??
  process.env.DATABASE_URL ??
  'sqlite+aiosqlite:///../backend/data/app.db'

const mockStructured = JSON.stringify({
  summary: 'Mock摘要',
  highlights: ['要点1', '要点2'],
  keywords: ['关键词A', '关键词B'],
})
const mockStructuredB64 = Buffer.from(mockStructured, 'utf8').toString('base64')

const backendEnvPrefix =
  process.platform === 'win32'
    ? `set DEBUG=1&& set DATABASE_URL=${backendDbUrl}&& set NEWS_AI_ENABLED=1&& set NEWS_AI_INTERVAL_SECONDS=1&& set NEWS_AI_BATCH_SIZE=200&& set NEWS_AI_SUMMARY_LLM_ENABLED=1&& set NEWS_AI_SUMMARY_LLM_MOCK_RESPONSE_B64=${mockStructuredB64}&& `
    : `DEBUG=1 DATABASE_URL=${backendDbUrl} NEWS_AI_ENABLED=1 NEWS_AI_INTERVAL_SECONDS=1 NEWS_AI_BATCH_SIZE=200 NEWS_AI_SUMMARY_LLM_ENABLED=1 NEWS_AI_SUMMARY_LLM_MOCK_RESPONSE_B64=${mockStructuredB64} `

const viteEnvPrefix =
  process.platform === 'win32'
    ? `set VITE_PROXY_TARGET=http://localhost:${backendPort}&& set VITE_WS_PROXY_TARGET=ws://localhost:${backendPort}&& `
    : `VITE_PROXY_TARGET=http://localhost:${backendPort} VITE_WS_PROXY_TARGET=ws://localhost:${backendPort} `

export default defineConfig({
  testDir: './tests/e2e',
  timeout: 60_000,
  forbidOnly: !!process.env.CI,
  fullyParallel: false,
  workers: 1,
  expect: {
    timeout: 12_000,
  },
  retries: process.env.CI ? 2 : 0,
  reporter: [['list'], ['html', { open: 'never' }]],
  use: {
    baseURL: `http://localhost:${frontendPort}`,
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
  },
  webServer: [
    {
      command: `${backendEnvPrefix}${pythonCmd} -m uvicorn app.main:app --app-dir ../backend --host 0.0.0.0 --port ${backendPort}`,
      url: `http://localhost:${backendPort}/health`,
      reuseExistingServer: reuseExistingBackend,
      timeout: 120_000,
    },
    {
      command: `${viteEnvPrefix}npm run dev -- --host 0.0.0.0 --port ${frontendPort}`,
      url: `http://localhost:${frontendPort}`,
      reuseExistingServer: reuseExistingFrontend,
      timeout: 120_000,
    },
  ],
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],
})
