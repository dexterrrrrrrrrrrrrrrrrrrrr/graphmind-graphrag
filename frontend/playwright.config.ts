import { defineConfig } from "@playwright/test";
export default defineConfig({
  testDir: "e2e",
  timeout: 90000,
  workers: 1,
  use: {
    baseURL: process.env.GRAPHMIND_E2E_BASE_URL || "http://127.0.0.1:5173",
    headless: true,
    launchOptions: {
      executablePath: process.env.CHROMIUM_PATH || undefined,
      args: ["--no-sandbox"],
    },
    screenshot: "only-on-failure",
  },
  reporter: "list",
});
