import { describe, it, expect } from "vitest";
import {
  getEditionDate,
  isBeforeEditionCutoff,
  isBeforeDeliveryTime,
  getUserLocalHourMinute,
} from "@/lib/edition-date";

// Helper: create a Date for a specific time in UTC
function utc(year: number, month: number, day: number, hour: number, minute = 0): Date {
  return new Date(Date.UTC(year, month - 1, day, hour, minute));
}

describe("getEditionDate", () => {
  it("returns today after 5 AM UTC", () => {
    const now = utc(2026, 3, 8, 10, 0); // 10:00 AM UTC
    expect(getEditionDate("UTC", now)).toBe("2026-03-08");
  });

  it("returns yesterday before 5 AM UTC", () => {
    const now = utc(2026, 3, 8, 4, 59); // 4:59 AM UTC
    expect(getEditionDate("UTC", now)).toBe("2026-03-07");
  });

  it("returns today at exactly 5 AM UTC", () => {
    const now = utc(2026, 3, 8, 5, 0); // 5:00 AM UTC
    expect(getEditionDate("UTC", now)).toBe("2026-03-08");
  });

  it("returns yesterday at midnight UTC", () => {
    const now = utc(2026, 3, 8, 0, 0); // midnight UTC
    expect(getEditionDate("UTC", now)).toBe("2026-03-07");
  });

  it("handles US/Eastern timezone (EDT in March = UTC-4)", () => {
    // 3:00 AM UTC = 11:00 PM EDT March 7
    // In ET, it's before 5 AM on March 8, so edition = March 7
    const now = utc(2026, 3, 8, 3, 0);
    expect(getEditionDate("US/Eastern", now)).toBe("2026-03-07");
  });

  it("handles US/Eastern after cutoff", () => {
    // 10:00 AM UTC = 6:00 AM EDT March 8 → after cutoff → March 8
    const now = utc(2026, 3, 8, 10, 0);
    expect(getEditionDate("US/Eastern", now)).toBe("2026-03-08");
  });

  it("handles US/Pacific timezone", () => {
    // 14:00 UTC = 6:00 AM PT (March 8) → after cutoff → March 8
    const now = utc(2026, 3, 8, 14, 0);
    expect(getEditionDate("US/Pacific", now)).toBe("2026-03-08");
  });

  it("handles year boundary", () => {
    // Jan 1 at 2 AM UTC → edition = Dec 31
    const now = utc(2026, 1, 1, 2, 0);
    expect(getEditionDate("UTC", now)).toBe("2025-12-31");
  });
});

describe("isBeforeEditionCutoff", () => {
  it("returns true before 5 AM", () => {
    expect(isBeforeEditionCutoff("UTC", utc(2026, 3, 8, 4, 59))).toBe(true);
  });

  it("returns false at 5 AM", () => {
    expect(isBeforeEditionCutoff("UTC", utc(2026, 3, 8, 5, 0))).toBe(false);
  });

  it("returns false after 5 AM", () => {
    expect(isBeforeEditionCutoff("UTC", utc(2026, 3, 8, 12, 0))).toBe(false);
  });

  it("respects timezone (EDT = UTC-4)", () => {
    // 8:00 AM UTC = 4:00 AM EDT → before cutoff
    expect(isBeforeEditionCutoff("US/Eastern", utc(2026, 3, 8, 8, 0))).toBe(true);
    // 9:00 AM UTC = 5:00 AM EDT → at cutoff
    expect(isBeforeEditionCutoff("US/Eastern", utc(2026, 3, 8, 9, 0))).toBe(false);
  });
});

describe("isBeforeDeliveryTime", () => {
  it("returns true before delivery time", () => {
    expect(isBeforeDeliveryTime("07:00", "UTC", utc(2026, 3, 8, 6, 30))).toBe(true);
  });

  it("returns false at delivery time", () => {
    expect(isBeforeDeliveryTime("07:00", "UTC", utc(2026, 3, 8, 7, 0))).toBe(false);
  });

  it("returns false after delivery time", () => {
    expect(isBeforeDeliveryTime("07:00", "UTC", utc(2026, 3, 8, 8, 0))).toBe(false);
  });

  it("handles half-hour delivery times", () => {
    expect(isBeforeDeliveryTime("06:30", "UTC", utc(2026, 3, 8, 6, 29))).toBe(true);
    expect(isBeforeDeliveryTime("06:30", "UTC", utc(2026, 3, 8, 6, 30))).toBe(false);
  });
});

describe("getUserLocalHourMinute", () => {
  it("returns correct hour and minute in UTC", () => {
    const { hour, minute } = getUserLocalHourMinute("UTC", utc(2026, 3, 8, 14, 35));
    expect(hour).toBe(14);
    expect(minute).toBe(35);
  });

  it("converts timezone correctly (EDT = UTC-4)", () => {
    // 15:00 UTC = 11:00 AM EDT
    const { hour } = getUserLocalHourMinute("US/Eastern", utc(2026, 3, 8, 15, 0));
    expect(hour).toBe(11);
  });
});
