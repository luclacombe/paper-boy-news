/**
 * OPDS Catalog Feed builder — pure function, no side effects.
 * Generates OPDS 1.2 Acquisition Feed (Atom XML) for KOReader.
 */

export interface OpdsEdition {
  id: string;
  editionDate: string;
  articleCount: number;
  sourceCount: number;
  fileSize: string;
  downloadUrl: string;
}

function escapeXml(str: string): string {
  return str
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&apos;");
}

function formatEditionDate(dateStr: string): string {
  const [year, month, day] = dateStr.split("-").map(Number);
  const date = new Date(year, month - 1, day);
  return date.toLocaleDateString("en-US", {
    weekday: "long",
    year: "numeric",
    month: "long",
    day: "numeric",
  });
}

export function buildOpdsFeed(
  editions: OpdsEdition[],
  title: string,
  selfUrl: string,
  profileId: string
): string {
  const updated =
    editions.length > 0
      ? `${editions[0].editionDate}T00:00:00Z`
      : new Date().toISOString();

  const entries = editions
    .map(
      (e) => `  <entry>
    <title>${escapeXml(title)} — ${escapeXml(formatEditionDate(e.editionDate))}</title>
    <id>urn:paperboy:edition:${escapeXml(e.id)}</id>
    <updated>${e.editionDate}T00:00:00Z</updated>
    <summary>${e.articleCount} articles from ${e.sourceCount} sources · ${escapeXml(e.fileSize)}</summary>
    <link rel="http://opds-spec.org/acquisition/open-access"
          href="${escapeXml(e.downloadUrl)}"
          type="application/epub+zip"
          title="Download EPUB"/>
  </entry>`
    )
    .join("\n");

  return `<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <id>urn:paperboy:user:${escapeXml(profileId)}</id>
  <title>${escapeXml(title)}</title>
  <subtitle>Your daily newspaper, built by Paper Boy News</subtitle>
  <updated>${updated}</updated>
  <author><name>Paper Boy News</name></author>
  <link rel="self" href="${escapeXml(selfUrl)}"
        type="application/atom+xml;profile=opds-catalog;kind=acquisition"/>
${entries}
</feed>
`;
}
