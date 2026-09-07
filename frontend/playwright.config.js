import { defineConfig } from "@playwright/test";
export default defineConfig({
  testDir: "./tests",
  use: {
    baseURL: "http://127.0.0.1:5174/static/",
    launchOptions: {
      executablePath: process.env.CHROME_BIN || "/usr/bin/google-chrome",
      args: ["--no-sandbox"],
    },
  },
  webServer: {
    command: "npm run dev -- --port 5174 --strictPort",
    url: "http://127.0.0.1:5174/static/",
    reuseExistingServer: false,
  },
});
