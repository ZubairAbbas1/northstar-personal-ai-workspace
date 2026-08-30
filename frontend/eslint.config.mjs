import { defineConfig, globalIgnores } from "eslint/config";
import nextVitals from "eslint-config-next/core-web-vitals";
import nextTypescript from "eslint-config-next/typescript";

export default defineConfig([
  ...nextVitals,
  ...nextTypescript,
  {
    // Preserve the project's existing TypeScript baseline while still running
    // Next.js accessibility, correctness, and hooks checks. The production
    // build remains strict and performs the full TypeScript type check.
    rules: {
      "@typescript-eslint/no-explicit-any": "off",
      "react-hooks/set-state-in-effect": "off",
      "react-hooks/purity": "off",
    },
  },
  globalIgnores([".next/**", ".next-dev/**", "next-env.d.ts"]),
]);
