/**
 * GitHub Actions integration.
 * Mirrors web/services/github_actions.py
 */

function getConfig(): { token: string; repo: string } | null {
  const token = process.env.GITHUB_TOKEN;
  const repo = process.env.GITHUB_REPO;
  if (!token || !repo) return null;
  return { token, repo };
}

export function isConfigured(): boolean {
  return getConfig() !== null;
}

export async function triggerBuild(): Promise<boolean> {
  const config = getConfig();
  if (!config) return false;

  const response = await fetch(
    `https://api.github.com/repos/${config.repo}/actions/workflows/daily-news.yml/dispatches`,
    {
      method: "POST",
      headers: {
        Authorization: `Bearer ${config.token}`,
        Accept: "application/vnd.github.v3+json",
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ ref: "main" }),
    }
  );

  return response.status === 204;
}

export interface GitHubBuild {
  date: string;
  status: string;
  statusLabel: string;
  runId: number;
  runUrl: string;
}

export async function getRecentBuilds(
  limit = 10
): Promise<GitHubBuild[]> {
  const config = getConfig();
  if (!config) return [];

  const response = await fetch(
    `https://api.github.com/repos/${config.repo}/actions/workflows/daily-news.yml/runs?per_page=${limit}`,
    {
      headers: {
        Authorization: `Bearer ${config.token}`,
        Accept: "application/vnd.github.v3+json",
      },
    }
  );

  if (!response.ok) return [];

  const data = await response.json();

  return (data.workflow_runs ?? []).map(
    (run: {
      created_at: string;
      status: string;
      conclusion: string | null;
      id: number;
      html_url: string;
    }) => {
      let statusLabel = "Building...";
      if (run.status === "completed") {
        statusLabel = run.conclusion === "success" ? "Delivered" : "Failed";
      } else if (run.status === "queued") {
        statusLabel = "Queued";
      }

      return {
        date: run.created_at,
        status: run.status,
        statusLabel,
        runId: run.id,
        runUrl: run.html_url,
      };
    }
  );
}
