import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: ".",
  timeout: 120_000,
  expect: { timeout: 30_000 },
  outputDir: "../apps/web/coverage/playwright",
  use: {
    baseURL: process.env.PLANTGUARD_E2E_URL ?? "http://127.0.0.1:8000",
    locale: "ru-RU",
    viewport: { width: 1440, height: 900 },
  },
});
