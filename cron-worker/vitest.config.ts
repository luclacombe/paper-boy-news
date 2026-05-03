import { cloudflareTest } from "@cloudflare/vitest-pool-workers";
import { defineConfig } from "vitest/config";

export default defineConfig({
  plugins: [
    cloudflareTest({
      wrangler: { configPath: "./wrangler.jsonc" },
      miniflare: {
        bindings: {
          GITHUB_PAT: "test-pat-not-real-do-not-use",
          GITHUB_REPO: "luclacombe/paper-boy",
        },
      },
    }),
  ],
});
