/**
 * Typed wrapper for GitHub repository_dispatch API.
 * Used to trigger EPUB builds in GitHub Actions.
 *
 * Server-side only — uses env vars never exposed to client.
 */

const GITHUB_PAT = process.env.GITHUB_PAT;
const GITHUB_REPO = process.env.GITHUB_REPO; // "owner/paper-boy"

export async function dispatchBuild(recordId: string): Promise<void> {
  if (!GITHUB_PAT || !GITHUB_REPO) {
    throw new Error("GitHub dispatch not configured (GITHUB_PAT or GITHUB_REPO missing)");
  }

  const res = await fetch(
    `https://api.github.com/repos/${GITHUB_REPO}/dispatches`,
    {
      method: "POST",
      headers: {
        Authorization: `token ${GITHUB_PAT}`,
        Accept: "application/vnd.github+json",
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        event_type: "build-newspaper",
        client_payload: { record_id: recordId },
      }),
    }
  );

  if (!res.ok && res.status !== 204) {
    const text = await res.text();
    throw new Error(`GitHub dispatch failed (${res.status}): ${text}`);
  }
}
