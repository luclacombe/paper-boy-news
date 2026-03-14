import { describe, it, expect } from "vitest";

// Test the BudgetBar logic directly (no React rendering needed)

describe("BudgetBar logic", () => {
  function getBarColor(ratio: number): string {
    if (ratio >= 0.8) return "green";
    if (ratio >= 0.5) return "amber";
    return "red";
  }

  function getPaperMinutes(
    sourceOutput: number,
    budget: number
  ): number {
    return sourceOutput >= budget
      ? budget
      : Math.round(sourceOutput);
  }

  function getHelperMessage(
    ratio: number,
    canFill: boolean,
    tooManySources: boolean,
    maxArticles: number,
  ): string | null {
    if (ratio === 0) return null;
    if (!canFill) return "Add more sources to fill your reading time.";
    if (tooManySources) return `Your paper fits ~${maxArticles} articles — sources are rotated so each gets featured.`;
    return "Articles are curated from your sources to match your reading time.";
  }

  it("returns green when sources fill ≥ 80% of budget", () => {
    expect(getBarColor(25 / 30)).toBe("green");
    expect(getBarColor(1.0)).toBe("green");
    expect(getBarColor(5.0)).toBe("green");
  });

  it("returns amber for ratio ≥ 0.5 and < 0.8", () => {
    expect(getBarColor(15 / 30)).toBe("amber");
    expect(getBarColor(0.5)).toBe("amber");
  });

  it("returns red for ratio < 0.5", () => {
    expect(getBarColor(5 / 30)).toBe("red");
    expect(getBarColor(0)).toBe("red");
  });

  it("caps paper minutes at budget when sources produce enough", () => {
    expect(getPaperMinutes(150, 20)).toBe(20);
  });

  it("shows raw output when sources produce less than budget", () => {
    expect(getPaperMinutes(12.4, 20)).toBe(12);
  });

  it("shows curation message when sources can fill budget", () => {
    const msg = getHelperMessage(1.5, true, false, 6);
    expect(msg).toContain("curated");
  });

  it("shows rotation message when too many sources", () => {
    // 10 sources, 10m budget, ~3m/article → maxArticles=3
    const msg = getHelperMessage(5.0, true, true, 3);
    expect(msg).toContain("rotated");
    expect(msg).toContain("~3");
  });

  it("shows add-more message when not enough sources", () => {
    const msg = getHelperMessage(0.4, false, false, 3);
    expect(msg).toContain("Add more");
  });
});
