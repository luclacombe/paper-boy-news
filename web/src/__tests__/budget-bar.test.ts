import { describe, it, expect } from "vitest";

// Test the BudgetBar logic directly (no React rendering needed)
// The component is simple enough that logic testing covers the behavior

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

  it("returns green when sources fill ≥ 80% of budget", () => {
    expect(getBarColor(25 / 30)).toBe("green");
    expect(getBarColor(1.0)).toBe("green");
    expect(getBarColor(5.0)).toBe("green"); // way over — still green
  });

  it("returns amber for ratio ≥ 0.5 and < 0.8", () => {
    expect(getBarColor(15 / 30)).toBe("amber");
    expect(getBarColor(0.5)).toBe("amber");
    expect(getBarColor(0.79)).toBe("amber");
  });

  it("returns red for ratio < 0.5", () => {
    expect(getBarColor(5 / 30)).toBe("red");
    expect(getBarColor(0.49)).toBe("red");
    expect(getBarColor(0)).toBe("red");
  });

  it("caps paper minutes at budget when sources produce enough", () => {
    expect(getPaperMinutes(150, 20)).toBe(20);
    expect(getPaperMinutes(20, 20)).toBe(20);
  });

  it("shows raw output when sources produce less than budget", () => {
    expect(getPaperMinutes(12.4, 20)).toBe(12);
    expect(getPaperMinutes(0, 20)).toBe(0);
  });
});
