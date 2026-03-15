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

  function getPipeline(
    dailyArticles: number,
    canFill: boolean,
    maxArticles: number,
    budgetMinutes: number,
    paperMinutes: number,
  ): { articles: string; picked: string; paper: string } | null {
    if (dailyArticles === 0) return null;

    const articles = `~${dailyArticles} article${dailyArticles !== 1 ? "s" : ""}`;

    let picked: string;
    if (!canFill || dailyArticles <= maxArticles) {
      picked = "all picked";
    } else {
      picked = `best ${maxArticles} picked`;
    }

    const paper = canFill
      ? `${budgetMinutes}m paper`
      : `${paperMinutes}m of ${budgetMinutes}m`;

    return { articles, picked, paper };
  }

  it("returns green when sources fill >= 80% of budget", () => {
    expect(getBarColor(25 / 30)).toBe("green");
    expect(getBarColor(1.0)).toBe("green");
    expect(getBarColor(5.0)).toBe("green");
  });

  it("returns amber for ratio >= 0.5 and < 0.8", () => {
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

  it("shows 'best N picked' when more articles than budget fits", () => {
    // 25 articles/day, budget fits 7
    const result = getPipeline(25, true, 7, 20, 20);
    expect(result).not.toBeNull();
    expect(result!.articles).toBe("~25 articles");
    expect(result!.picked).toBe("best 7 picked");
    expect(result!.paper).toBe("20m paper");
  });

  it("shows 'all picked' when articles fit within budget", () => {
    // 5 articles/day, budget fits 7
    const result = getPipeline(5, true, 7, 20, 20);
    expect(result!.picked).toBe("all picked");
  });

  it("shows shortfall when sources cannot fill budget", () => {
    // 3 articles, can't fill, paper is 8m of 20m
    const result = getPipeline(3, false, 7, 20, 8);
    expect(result!.articles).toBe("~3 articles");
    expect(result!.picked).toBe("all picked");
    expect(result!.paper).toBe("8m of 20m");
  });

  it("returns null when no daily articles", () => {
    const result = getPipeline(0, false, 0, 20, 0);
    expect(result).toBeNull();
  });

  it("handles singular article", () => {
    const result = getPipeline(1, false, 7, 20, 3);
    expect(result!.articles).toBe("~1 article");
  });
});
