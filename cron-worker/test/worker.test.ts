import {
  createExecutionContext,
  createScheduledController,
  env,
  waitOnExecutionContext,
} from "cloudflare:test";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import worker from "../src/index";

const BUILD_CRON = "45 3,7,11,15,19,23 * * *";
const DELIVER_CRON = "*/30 * * * *";

type CapturedRequest = {
  url: string;
  method: string;
  headers: Record<string, string>;
  body: unknown;
};

function spyFetch(response: Response): {
  spy: ReturnType<typeof vi.fn>;
  captured: CapturedRequest[];
} {
  const captured: CapturedRequest[] = [];
  const spy = vi.fn(async (input: Request | string | URL, init?: RequestInit) => {
    const url = typeof input === "string" || input instanceof URL ? input.toString() : input.url;
    const method = init?.method ?? (input instanceof Request ? input.method : "GET");
    const headers = headersToObject(init?.headers ?? (input instanceof Request ? input.headers : undefined));
    let body: unknown = init?.body;
    if (typeof body === "string") {
      try {
        body = JSON.parse(body);
      } catch {
        // leave as string
      }
    }
    captured.push({ url, method, headers, body });
    return response.clone();
  });
  vi.stubGlobal("fetch", spy);
  return { spy, captured };
}

function headersToObject(h: HeadersInit | Headers | undefined): Record<string, string> {
  if (!h) return {};
  if (h instanceof Headers) {
    const out: Record<string, string> = {};
    h.forEach((v, k) => {
      out[k.toLowerCase()] = v;
    });
    return out;
  }
  if (Array.isArray(h)) {
    return Object.fromEntries(h.map(([k, v]) => [k.toLowerCase(), v]));
  }
  return Object.fromEntries(Object.entries(h).map(([k, v]) => [k.toLowerCase(), String(v)]));
}

describe("scheduled handler", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it.each([
    [BUILD_CRON, "build"],
    [DELIVER_CRON, "deliver"],
  ])("dispatches event_type=%s for cron %s", async (cron, expectedEventType) => {
    const { captured } = spyFetch(new Response(null, { status: 204 }));

    const controller = createScheduledController({ scheduledTime: new Date(), cron });
    const ctx = createExecutionContext();
    await worker.scheduled(controller, env, ctx);
    await waitOnExecutionContext(ctx);

    expect(captured).toHaveLength(1);
    const req = captured[0];
    expect(req.url).toBe("https://api.github.com/repos/luclacombe/paper-boy-news/dispatches");
    expect(req.method).toBe("POST");
    expect(req.headers["authorization"]).toBe(`Bearer ${env.GITHUB_PAT}`);
    expect(req.headers["user-agent"]).toBe("paper-boy-cron-worker");
    expect(req.headers["accept"]).toBe("application/vnd.github+json");
    expect(req.headers["x-github-api-version"]).toBe("2026-03-10");
    expect(req.headers["content-type"]).toBe("application/json");
    expect(req.body).toEqual({ event_type: expectedEventType });
  });

  it("does not throw when GitHub returns 500", async () => {
    spyFetch(new Response("internal error", { status: 500 }));
    const errorSpy = vi.spyOn(console, "error").mockImplementation(() => {});

    const controller = createScheduledController({
      scheduledTime: new Date(),
      cron: DELIVER_CRON,
    });
    const ctx = createExecutionContext();

    await expect(worker.scheduled(controller, env, ctx)).resolves.not.toThrow();
    await waitOnExecutionContext(ctx);

    expect(errorSpy).toHaveBeenCalled();
    expect(errorSpy.mock.calls[0].join(" ")).toContain("500");
  });

  it("does not throw when fetch itself rejects (network error)", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() => Promise.reject(new Error("network down"))),
    );
    const errorSpy = vi.spyOn(console, "error").mockImplementation(() => {});

    const controller = createScheduledController({
      scheduledTime: new Date(),
      cron: DELIVER_CRON,
    });
    const ctx = createExecutionContext();

    await expect(worker.scheduled(controller, env, ctx)).resolves.not.toThrow();
    await waitOnExecutionContext(ctx);

    expect(errorSpy).toHaveBeenCalled();
  });

  it("never logs the GITHUB_PAT value, in any path", async () => {
    const logSpy = vi.spyOn(console, "log").mockImplementation(() => {});
    const errorSpy = vi.spyOn(console, "error").mockImplementation(() => {});
    const warnSpy = vi.spyOn(console, "warn").mockImplementation(() => {});

    // Success path
    spyFetch(new Response(null, { status: 204 }));
    let ctx = createExecutionContext();
    await worker.scheduled(
      createScheduledController({ scheduledTime: new Date(), cron: DELIVER_CRON }),
      env,
      ctx,
    );
    await waitOnExecutionContext(ctx);

    // Failure path (HTTP error)
    spyFetch(new Response(`oops with token ${env.GITHUB_PAT} echoed`, { status: 401 }));
    ctx = createExecutionContext();
    await worker.scheduled(
      createScheduledController({ scheduledTime: new Date(), cron: BUILD_CRON }),
      env,
      ctx,
    );
    await waitOnExecutionContext(ctx);

    // Note: we deliberately put the PAT in the response body above to make
    // sure the worker itself doesn't accidentally surface response bodies
    // containing it. If your worker echoes res.text(), this catches it.
    const allOutput = [
      ...logSpy.mock.calls,
      ...errorSpy.mock.calls,
      ...warnSpy.mock.calls,
    ]
      .flat()
      .map((arg) => (typeof arg === "string" ? arg : JSON.stringify(arg)))
      .join(" ");

    expect(allOutput).not.toContain(env.GITHUB_PAT);
  });

  it("warns and does not dispatch on unknown cron", async () => {
    const { spy } = spyFetch(new Response(null, { status: 204 }));
    const warnSpy = vi.spyOn(console, "warn").mockImplementation(() => {});

    const controller = createScheduledController({
      scheduledTime: new Date(),
      cron: "0 0 * * *", // not in our triggers
    });
    const ctx = createExecutionContext();
    await worker.scheduled(controller, env, ctx);
    await waitOnExecutionContext(ctx);

    expect(spy).not.toHaveBeenCalled();
    expect(warnSpy).toHaveBeenCalled();
    expect(warnSpy.mock.calls[0].join(" ")).toContain("0 0 * * *");
  });
});

describe("fetch (healthcheck)", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("returns 200 with JSON status and the configured crons", async () => {
    const ctx = createExecutionContext();
    const res = await worker.fetch(new Request("https://example.com/"), env, ctx);
    await waitOnExecutionContext(ctx);

    expect(res.status).toBe(200);
    expect(res.headers.get("content-type")).toMatch(/application\/json/);
    const body = (await res.json()) as { status: string; crons: string[] };
    expect(body.status).toBe("ok");
    expect(body.crons).toContain(BUILD_CRON);
    expect(body.crons).toContain(DELIVER_CRON);
  });
});
