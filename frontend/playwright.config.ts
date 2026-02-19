import path from "path";
import { defineConfig, devices } from "@playwright/test";
import dotenv from "dotenv";
dotenv.config();

const FRONTEND_URL = process.env.FRONTEND_URL ?? "http://localhost:3000";
const API_URL = process.env.API_URL ?? "http://localhost:8000";
const USE_TEST_DB = process.env.USE_TEST_DB !== "0";

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: 1,
  reporter: "html",
  use: {
    baseURL: FRONTEND_URL,
    trace: "on-first-retry",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: USE_TEST_DB
    ? [
        {
          command: "python run_with_test_db.py",
          url: `${API_URL}/health`,
          reuseExistingServer: !process.env.CI,
          timeout: 60000,
          cwd: path.join(__dirname, "..", "backend"),
        },
        {
          command: "npm run dev",
          url: FRONTEND_URL,
          reuseExistingServer: !process.env.CI,
          timeout: 120000,
        },
      ]
    : {
        command: "npm run dev",
        url: FRONTEND_URL,
        reuseExistingServer: !process.env.CI,
        timeout: 120000,
      },
});
