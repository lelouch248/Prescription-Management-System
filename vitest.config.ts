import { defineConfig } from "vitest/config";

export default defineConfig({
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./src/frontend/test-setup.ts"],
    include: ["src/frontend/**/*.test.{ts,tsx}"],
  },
});
