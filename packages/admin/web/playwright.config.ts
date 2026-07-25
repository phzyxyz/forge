import { defineConfig } from "@playwright/test";

const onCi = Boolean(process.env.CI);

export default defineConfig({
  testDir: "./e2e",
  timeout: 90_000,
  // Shared demo SQLite — parallel files race mutations; serialize on CI.
  fullyParallel: false,
  workers: onCi ? 1 : undefined,
  retries: onCi ? 2 : 0,
  use: {
    baseURL: process.env.ADMINBOARD_BASE_URL || "http://127.0.0.1:9100",
    headless: true,
    trace: "on-first-retry",
    actionTimeout: 20_000,
    navigationTimeout: 30_000,
  },
  projects: [{ name: "chromium", use: { browserName: "chromium" } }],
});
