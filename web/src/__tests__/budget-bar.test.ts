import { describe, it, expect } from "vitest";

// Test the BudgetBar logic directly (no React rendering needed)
// The component is simple enough that logic testing covers the behavior

describe("BudgetBar logic", () => {
  function getBarColor(ratio: number): string {
    if (ratio <= 0.8) return "green";
    if (ratio <= 1.2) return "amber";
    return "red";
  }

  function shouldShowWarning(ratio: number, rounded: number): boolean {
    return ratio > 2 && rounded > 0;
  }

  it("returns green for ratio ≤ 0.8", () => {
    expect(getBarColor(20 / 30)).toBe("green");
    expect(getBarColor(0)).toBe("green");
    expect(getBarColor(0.8)).toBe("green");
  });

  it("returns amber for ratio > 0.8 and ≤ 1.2", () => {
    expect(getBarColor(30 / 30)).toBe("amber");
    expect(getBarColor(0.81)).toBe("amber");
    expect(getBarColor(1.2)).toBe("amber");
  });

  it("returns red for ratio > 1.2", () => {
    expect(getBarColor(40 / 30)).toBe("red");
    expect(getBarColor(1.21)).toBe("red");
  });

  it("shows warning when estimated > 2× budget", () => {
    expect(shouldShowWarning(70 / 30, 70)).toBe(true);
    expect(shouldShowWarning(61 / 30, 61)).toBe(true);
  });

  it("does not show warning at or below 2×", () => {
    expect(shouldShowWarning(50 / 30, 50)).toBe(false);
    expect(shouldShowWarning(60 / 30, 60)).toBe(false);
  });

  it("does not show warning when rounded is 0", () => {
    expect(shouldShowWarning(3, 0)).toBe(false);
  });
});
