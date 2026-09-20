import path from "node:path";
import { defineConfig } from "@rstest/core";

const root = import.meta.dirname;

/**
 * Tests for the pure layers: payload readers, stream summaries, kind
 * resolution. Components are not rendered here — the shell and the product
 * components are screenshot-baseline territory, not unit-test territory.
 */
export default defineConfig({
  root,
  include: ["tests/**/*.test.ts"],
  resolve: {
    alias: {
      "@": path.resolve(root, "src"),
    },
  },
});
