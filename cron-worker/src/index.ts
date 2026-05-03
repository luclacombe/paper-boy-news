/**
 * paper-boy-cron — Cloudflare Worker that fires GitHub repository_dispatch
 * events on a reliable schedule.
 *
 * Replaces GitHub Actions' unreliable cron triggers (which routinely drift
 * by 20+ minutes or skip slots entirely). The existing GH workflow stays
 * as the worker — only scheduling moves here.
 *
 * Two cron triggers map to two dispatch event types — see the BUILD_CRON
 * and DELIVER_CRON constants below for the exact expressions. The cron
 * strings are matched against controller.cron and MUST be character-
 * identical to the values in wrangler.jsonc.
 */

const BUILD_CRON = "45 3,7,11,15,19,23 * * *";
const DELIVER_CRON = "*/30 * * * *";

type EventType = "build" | "deliver";

async function dispatch(env: Env, eventType: EventType): Promise<void> {
  const url = `https://api.github.com/repos/${env.GITHUB_REPO}/dispatches`;
  let res: Response;
  try {
    res = await fetch(url, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${env.GITHUB_PAT}`,
        Accept: "application/vnd.github+json",
        "X-GitHub-Api-Version": "2026-03-10",
        "Content-Type": "application/json",
        "User-Agent": "paper-boy-cron-worker",
      },
      body: JSON.stringify({ event_type: eventType }),
    });
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    console.error(`[${eventType}] dispatch network error: ${msg}`);
    return;
  }

  if (res.status === 204) {
    console.log(`[${eventType}] dispatched`);
    return;
  }

  console.error(`[${eventType}] dispatch failed: HTTP ${res.status}`);
}

export default {
  async scheduled(
    controller: ScheduledController,
    env: Env,
    ctx: ExecutionContext,
  ): Promise<void> {
    switch (controller.cron) {
      case BUILD_CRON:
        ctx.waitUntil(dispatch(env, "build"));
        break;
      case DELIVER_CRON:
        ctx.waitUntil(dispatch(env, "deliver"));
        break;
      default:
        console.warn(`Unknown cron expression: ${controller.cron}`);
    }
  },

  async fetch(_request: Request, _env: Env, _ctx: ExecutionContext): Promise<Response> {
    const body = JSON.stringify({
      status: "ok",
      service: "paper-boy-cron",
      crons: [BUILD_CRON, DELIVER_CRON],
    });
    return new Response(body, {
      headers: {
        "Content-Type": "application/json",
        "Cache-Control": "no-store",
      },
    });
  },
} satisfies ExportedHandler<Env>;
