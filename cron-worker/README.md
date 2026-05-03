# paper-boy-cron — Cloudflare Worker

A small Cloudflare Worker that fires GitHub `repository_dispatch` events
on a reliable schedule, replacing GitHub Actions' unreliable cron
triggers.

## Why this exists

GH Actions `schedule:` triggers do not guarantee on-time execution. In
the 48 h before the delivery-reliability audit (PR 1):

| metric | value |
|---|---|
| build cron on-time | 0 / 13 |
| build cron median lateness | 20 min (max 70) |
| deliver cron slots that never fired | 25 % |
| deliver cron slots > 15 min late | 76 % of fires |

Cloudflare Workers Cron Triggers fire on time. The existing
`.github/workflows/build-newspaper.yml` keeps doing the actual work —
this worker only changes who pulls the trigger. See
[`docs/superpowers/plans/2026-05-03-cf-worker-cron.md`](../docs/superpowers/plans/2026-05-03-cf-worker-cron.md)
for the design.

## How it works

```
CF Worker (this dir)                  GitHub Actions
─────────────────────                 ─────────────────────
scheduled()                           repository_dispatch:
  controller.cron switches on:          types: [build-newspaper, build, deliver]
    "45 3,7,11,15,19,23 * * *"  ───→  Set BUILD_MODE → build → run_build_all()
    "*/30 * * * *"              ───→  Set BUILD_MODE → deliver → run_deliver()
  POST .../dispatches               
    body: {"event_type": "build" | "deliver"}
```

`fetch()` exposes a healthcheck at `GET /` that returns the configured
crons as JSON.

The legacy GH `schedule:` triggers are still active as a safety net
during the migration. Removing them is a separate follow-up PR after
7 days of clean CF operation. Double-firing is harmless: the build
script's `status != 'failed'` skip and the PR 1 recency cap +
`resend_message_id` idempotency together make a duplicate dispatch a
no-op.

## Prerequisites

1. **Cloudflare account** — free tier is sufficient. Sign up at
   https://dash.cloudflare.com. No payment method required.

2. **Wrangler CLI**:
   ```
   npm i -g wrangler
   wrangler login
   ```

3. **Fine-grained GitHub PAT** — generated at
   https://github.com/settings/personal-access-tokens.
   - Resource owner: `luclacombe`
   - Repository access: only `paper-boy`
   - Repository permissions:
     - **Contents: Read and write** ← required for `repository_dispatch`
     - Metadata: Read (auto-selected)
     - Actions: leave at none — that's for `workflow_dispatch`, a
       different endpoint. Granting it here gives the token unnecessary
       reach.
   - Expiration: 1 year
   - Save the value (shown only once).

   > ⚠️ The contents permission requirement is non-obvious. The first
   > 403 response you'll see if you give it `Actions: Read and write`
   > instead is "Resource not accessible by personal access token".
   > See [Elio Struyf's writeup](https://www.eliostruyf.com/dispatch-github-action-fine-grained-personal-access-token/)
   > and the [GitHub docs](https://docs.github.com/en/rest/authentication/permissions-required-for-fine-grained-personal-access-tokens).

## Deploy from scratch

```bash
cd cron-worker
npm install
wrangler secret put GITHUB_PAT     # paste the PAT (input is hidden, not echoed)
wrangler deploy
```

Verify in the [Cloudflare dashboard](https://dash.cloudflare.com):
- Workers & Pages → `paper-boy-cron`
- **Triggers** tab — both crons listed
  - `45 3,7,11,15,19,23 * * *`
  - `*/30 * * * *`
- **Logs** tab (live tail) — wait up to 30 minutes for the next deliver
  fire. Expect a single line:
  `[deliver] dispatched`
- In the GitHub repo's **Actions** tab — a `repository_dispatch` event
  fires `build-newspaper.yml` within ~30 s. The `Set BUILD_MODE` step's
  log will show `Resolved BUILD_MODE='deliver' …`.

## Rotate the GitHub PAT

Generate a fresh PAT (same scopes — Contents: Read & write), then:

```bash
cd cron-worker
wrangler secret put GITHUB_PAT     # overwrites the existing secret
```

No redeploy needed; the secret is read at fetch time. Propagation is
typically a few seconds. Revoke the old PAT in GitHub once the next
fire succeeds.

## Disable temporarily

Two options.

**Comment out the cron triggers and redeploy:**

```bash
# In wrangler.jsonc, remove (or comment) the "triggers" block.
wrangler deploy
```

The worker stays deployed (so its URL keeps responding to healthchecks),
but no scheduled invocations fire. To re-enable, restore the block and
redeploy. The GH Actions `schedule:` safety net will keep the build
running while CF is paused.

**Or fully remove the worker:**

```bash
wrangler delete paper-boy-cron
```

You'll need to re-deploy from scratch to bring it back. The GH safety
net still runs.

## Logs

- **Cloudflare dashboard** → Workers & Pages → `paper-boy-cron` →
  **Logs** (live tail, ~24 h retention on free plan).
- **Local tail**:
  ```
  cd cron-worker
  wrangler tail
  ```

The worker logs `[build] dispatched` / `[deliver] dispatched` on
success and `[<type>] dispatch failed: HTTP <status>` (or
`[<type>] dispatch network error: <message>`) on failure. Failures are
logged but do not throw — the next scheduled fire retries from scratch.

## Local development

```bash
cd cron-worker
npm install
npm run dev    # = wrangler dev --test-scheduled
```

Trigger a fake fire from another terminal:

```bash
# build cron
curl "http://localhost:8787/__scheduled?cron=45+3,7,11,15,19,23+*+*+*"

# deliver cron
curl "http://localhost:8787/__scheduled?cron=*%2F30+*+*+*+*"
```

The worker won't actually fire a real `repository_dispatch` if you
haven't put a real PAT into `.dev.vars` (gitignored), and it'll log a
401 from GitHub when running with the test secret. That's expected and
keeps you from accidentally dispatching from local.

## Tests

```bash
cd cron-worker
npm test                  # vitest run
npm run typecheck         # tsc --noEmit
npm run deploy:dry        # wrangler deploy --dry-run --outdir=dist
```

The test suite (`test/worker.test.ts`) runs inside a real `workerd`
runtime via `@cloudflare/vitest-pool-workers` and asserts:
- correct dispatch URL, headers (`Bearer …`, User-Agent,
  `X-GitHub-Api-Version`, `Accept`), and body for each cron
- the worker doesn't throw when GitHub returns 500 or the network
  drops
- the PAT value never appears in any console output (success or
  failure path)
- the `fetch()` healthcheck returns 200 with the expected JSON
- an unknown cron expression triggers a warning, not a dispatch

## Why these specific design choices

- **Only `GITHUB_PAT` is a secret**; `GITHUB_REPO` is a Wrangler `var`.
  The repo name is in every commit URL — there's nothing to hide.
- **`User-Agent: paper-boy-cron-worker`** is set explicitly. The
  GitHub API rejects requests with an empty/missing User-Agent header
  with a 403.
- **Errors are logged, not thrown.** A thrown error doesn't generate
  any operator notification on the free CF tier; it just adds noise to
  the dashboard. PR 3 will add an external healthcheck heartbeat
  (Healthchecks.io / BetterStack) that catches sustained outages.
- **`controller.cron` is matched as a string.** The cron expressions
  in `src/index.ts` MUST be character-identical to the ones in
  `wrangler.jsonc`. The test suite verifies dispatching happens for
  each cron in the config, so a drift between the two files surfaces
  immediately.

## Free-plan budget

| limit | value | usage |
|---|---|---|
| requests / day | 100 000 | 54 (6 build + 48 deliver) |
| cron triggers / account | 5 | 2 |
| CPU / cron fire | 10 ms | ~1 ms (one outbound fetch) |

A future expansion (e.g., adding a healthcheck cron in PR 3) leaves
ample headroom on the free plan.
