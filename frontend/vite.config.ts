import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    strictPort: true,
    // Preserve the browser's Origin so the API can enforce APP_ORIGIN.
    proxy: {
      "/api": { target: process.env.API_PROXY_TARGET ?? "http://127.0.0.1:8000" },
    },
  },
  test: {
    include: ["src/**/*.test.{ts,tsx}"],
    environment: "jsdom",
    setupFiles: ["./src/test-setup.ts"],
    clearMocks: true,
    coverage: {
      provider: "v8",
      include: ["src/**/*.{ts,tsx}"],
      exclude: ["src/**/*.test.{ts,tsx}", "src/test-setup.ts", "src/**/*.d.ts"],
      reporter: ["text", "json-summary", "html", "lcov"],
      reportsDirectory: "coverage",
    },
  },
});
