import { describe, it, expect } from "vitest";
import { buildOpdsFeed, type OpdsEdition } from "@/lib/opds";

function makeEdition(overrides: Partial<OpdsEdition> = {}): OpdsEdition {
  return {
    id: "aaaaaaaa-1111-2222-3333-444444444444",
    editionDate: "2026-03-11",
    articleCount: 15,
    sourceCount: 5,
    fileSize: "1.2 MB",
    downloadUrl: "https://example.com/api/opds/abc123/download/aaaaaaaa-1111-2222-3333-444444444444",
    ...overrides,
  };
}

describe("buildOpdsFeed", () => {
  it("returns valid XML with correct namespace", () => {
    const xml = buildOpdsFeed([], "My Paper", "https://example.com/feed.xml", "profile-1");
    expect(xml).toContain('<?xml version="1.0" encoding="UTF-8"?>');
    expect(xml).toContain('xmlns="http://www.w3.org/2005/Atom"');
    expect(xml).toContain("<title>My Paper</title>");
    expect(xml).toContain("urn:paperboy:user:profile-1");
  });

  it("includes all editions with download links", () => {
    const editions = [
      makeEdition({ id: "ed-1", editionDate: "2026-03-11" }),
      makeEdition({ id: "ed-2", editionDate: "2026-03-10" }),
    ];
    const xml = buildOpdsFeed(editions, "News", "https://example.com/feed.xml", "p1");
    expect(xml).toContain("urn:paperboy:edition:ed-1");
    expect(xml).toContain("urn:paperboy:edition:ed-2");
    expect(xml).toContain('rel="http://opds-spec.org/acquisition/open-access"');
    expect(xml).toContain('type="application/epub+zip"');
  });

  it("empty editions produces feed with no entries", () => {
    const xml = buildOpdsFeed([], "Paper", "https://example.com/feed.xml", "p1");
    expect(xml).toContain("<feed");
    expect(xml).toContain("</feed>");
    expect(xml).not.toContain("<entry>");
  });

  it("escapes XML special characters in titles", () => {
    const xml = buildOpdsFeed([], "News & Views <Today>", "https://example.com/feed.xml", "p1");
    expect(xml).toContain("News &amp; Views &lt;Today&gt;");
    expect(xml).not.toContain("News & Views <Today>");
  });

  it("includes edition metadata in summary", () => {
    const editions = [makeEdition({ articleCount: 15, sourceCount: 5, fileSize: "1.2 MB" })];
    const xml = buildOpdsFeed(editions, "Paper", "https://example.com/feed.xml", "p1");
    expect(xml).toContain("15 articles from 5 sources · 1.2 MB");
  });

  it("formats edition dates in entry titles", () => {
    const editions = [makeEdition({ editionDate: "2026-03-11" })];
    const xml = buildOpdsFeed(editions, "Paper", "https://example.com/feed.xml", "p1");
    expect(xml).toContain("Wednesday, March 11, 2026");
  });

  it("uses latest edition date for feed updated element", () => {
    const editions = [
      makeEdition({ editionDate: "2026-03-11" }),
      makeEdition({ editionDate: "2026-03-10" }),
    ];
    const xml = buildOpdsFeed(editions, "Paper", "https://example.com/feed.xml", "p1");
    expect(xml).toContain("<updated>2026-03-11T00:00:00Z</updated>");
  });

  it("includes self link with OPDS content type", () => {
    const xml = buildOpdsFeed([], "Paper", "https://example.com/feed.xml", "p1");
    expect(xml).toContain('rel="self"');
    expect(xml).toContain('href="https://example.com/feed.xml"');
    expect(xml).toContain("application/atom+xml;profile=opds-catalog;kind=acquisition");
  });
});
