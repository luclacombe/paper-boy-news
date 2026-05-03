/**
 * Augments `Cloudflare.Env` with bindings that aren't visible to
 * `wrangler types` — secrets (set via `wrangler secret put`).
 *
 * `wrangler.jsonc`-defined `vars` (e.g. GITHUB_REPO) are picked up
 * automatically and live in `worker-configuration.d.ts`. This file
 * adds the runtime-only bindings so `Env` is typed correctly in both
 * the worker and the test suite.
 *
 * No `import`/`export` here on purpose — this file must stay an
 * ambient script so the `Cloudflare` namespace augmentation merges
 * with the one in the generated worker-configuration.d.ts globally.
 */
declare namespace Cloudflare {
  interface Env {
    /** Fine-grained GitHub PAT — Contents: Read & Write on the target repo. */
    GITHUB_PAT: string;
  }
}
