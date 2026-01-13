import { defineConfig, devices } from "@playwright/test";

const proc: any = (globalThis as any).process;
const buf: any = (globalThis as any).Buffer;

const pythonCmd = proc?.platform === "win32" ? "py" : "python";
const e2eHost = proc?.env?.E2E_HOST ?? "127.0.0.1";
const backendPort = Number(proc?.env?.E2E_BACKEND_PORT ?? 8001);
const frontendPort = Number(proc?.env?.E2E_FRONTEND_PORT ?? 5174);
const reuseExistingBackend =
  !proc?.env?.CI && proc?.env?.E2E_REUSE_EXISTING === "1";
const reuseExistingFrontend =
  !proc?.env?.CI && proc?.env?.E2E_REUSE_EXISTING === "1";

if (proc?.env) {
  proc.env.E2E_API_BASE =
    proc.env.E2E_API_BASE ?? `http://${e2eHost}:${frontendPort}/api`;
}

const backendDbUrl =
  proc?.env?.E2E_DATABASE_URL ??
  proc?.env?.DATABASE_URL ??
  "sqlite+aiosqlite:///../backend/data/e2e_playwright.db";

const mockStructured = JSON.stringify({
  summary: "Mock摘要",
  highlights: ["要点1", "要点2"],
  keywords: ["关键词A", "关键词B"],
});
const mockStructuredB64 = buf.from(mockStructured, "utf8").toString(
  "base64"
);

const frontendBaseUrl = proc?.env?.E2E_FRONTEND_BASE_URL ?? `http://${e2eHost}:${frontendPort}`;

const backendEnvPrefix =
  proc?.platform === "win32"
    ? `set PYTHONIOENCODING=utf-8&& set E2E_SEED=1&& set DEBUG=1&& set DATABASE_URL=${backendDbUrl}&& set FRONTEND_BASE_URL=${frontendBaseUrl}&& set NEWS_AI_ENABLED=1&& set NEWS_AI_INTERVAL_SECONDS=1&& set NEWS_AI_BATCH_SIZE=200&& set NEWS_AI_SUMMARY_LLM_ENABLED=1&& set NEWS_AI_SUMMARY_LLM_MOCK_RESPONSE_B64=${mockStructuredB64}&& `
    : `PYTHONIOENCODING=utf-8 E2E_SEED=1 DEBUG=1 DATABASE_URL=${backendDbUrl} FRONTEND_BASE_URL=${frontendBaseUrl} NEWS_AI_ENABLED=1 NEWS_AI_INTERVAL_SECONDS=1 NEWS_AI_BATCH_SIZE=200 NEWS_AI_SUMMARY_LLM_ENABLED=1 NEWS_AI_SUMMARY_LLM_MOCK_RESPONSE_B64=${mockStructuredB64} `;

const viteEnvPrefix =
  proc?.platform === "win32"
    ? `set VITE_PROXY_TARGET=http://${e2eHost}:${backendPort}&& set VITE_WS_PROXY_TARGET=ws://${e2eHost}:${backendPort}&& `
    : `VITE_PROXY_TARGET=http://${e2eHost}:${backendPort} VITE_WS_PROXY_TARGET=ws://${e2eHost}:${backendPort} `;

export default defineConfig({
  testDir: "./tests/e2e",
  timeout: 60_000,
  forbidOnly: !!proc?.env?.CI,
  fullyParallel: false,
  workers: 1,
  expect: {
    timeout: 12_000,
  },
  retries: proc?.env?.CI ? 2 : 0,
  reporter: [["list"], ["html", { open: "never" }]],
  use: {
    baseURL: `http://${e2eHost}:${frontendPort}`,
    locale: "zh-CN",
    trace: "on-first-retry",
    screenshot: "only-on-failure",
    video: "retain-on-failure",
  },
  webServer: [
    {
      command: `${backendEnvPrefix}${pythonCmd} ../backend/scripts/seed_data.py && ${pythonCmd} -m uvicorn app.main:app --app-dir ../backend --host 0.0.0.0 --port ${backendPort}`,
      url: `http://${e2eHost}:${backendPort}/health`,
      reuseExistingServer: reuseExistingBackend,
      timeout: 120_000,
    },
    {
      command: `${viteEnvPrefix}npm run dev -- --host 0.0.0.0 --port ${frontendPort} --logLevel error`,
      url: `http://${e2eHost}:${frontendPort}`,
      reuseExistingServer: reuseExistingFrontend,
      timeout: 120_000,
    },
  ],
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
});
