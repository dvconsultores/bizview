import { defineConfig, devices } from "@playwright/test";

// Browser matrix of FR-027 / SC-006 at the phone widths of SC-005.
const widths = [320, 375];
const engines = [
  { name: "chromium", use: devices["Desktop Chrome"] },
  {
    name: "firefox",
    // Host veth churn makes Firefox abort idle in-flight requests; keep the assistant POST alive.
    use: { ...devices["Desktop Firefox"], launchOptions: { firefoxUserPrefs: { "network.notify.changed": false } } },
  },
  { name: "webkit", use: devices["iPhone 12"] },
];

export default defineConfig({
  testDir: "tests/e2e",
  globalTeardown: "./tests/e2e/teardown.ts",
  fullyParallel: false,
  workers: 1,
  retries: 0,
  // The backend talks to the external BI database (~180 ms per round trip), so flows are slower
  // than against a local database.
  timeout: 60_000,
  expect: { timeout: 10_000 },
  reporter: [["list"]],
  use: { baseURL: "http://localhost:4173", locale: "es-ES", trace: "retain-on-failure", reducedMotion: "reduce" },
  projects: engines.flatMap((e) =>
    widths.map((w) => ({
      name: `${e.name}-${w}`,
      use: { ...e.use, viewport: { width: w, height: 740 }, deviceScaleFactor: 2 },
    })),
  ),
  // The backend rebuilds a throwaway schema on every run: 20 migrations plus the workspace seed,
  // each statement crossing ~180 ms to the external BI database, so the readiness ceiling is
  // minutes rather than seconds (it is a maximum wait, not a fixed delay).
  webServer: [
    { command: "sh tests/e2e/backend.sh", url: "http://localhost:8001/api/health", reuseExistingServer: false, timeout: 420_000 },
    { command: "npm run build && API_TARGET=http://localhost:8001 npx vite preview --port 4173 --strictPort", url: "http://localhost:4173", reuseExistingServer: false, timeout: 240_000 },
  ],
});
