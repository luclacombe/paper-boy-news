import { EDITION_ROLLOVER_HOUR } from "@/lib/constants";

/**
 * Get date parts (YYYY-MM-DD, hour, minute) in a specific timezone.
 * Uses Intl.DateTimeFormat — no external dependencies.
 */
function getDatePartsInTZ(
  timezone: string,
  now: Date = new Date()
): { date: string; hour: number; minute: number } {
  const formatter = new Intl.DateTimeFormat("en-CA", {
    timeZone: timezone,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  });
  const map = Object.fromEntries(
    formatter.formatToParts(now).map((p) => [p.type, p.value])
  );
  return {
    date: `${map.year}-${map.month}-${map.day}`,
    hour: parseInt(map.hour, 10),
    minute: parseInt(map.minute, 10),
  };
}

/** Subtract one calendar day from a YYYY-MM-DD string. */
function subtractOneDay(dateStr: string): string {
  const [y, m, d] = dateStr.split("-").map(Number);
  const dt = new Date(Date.UTC(y, m - 1, d));
  dt.setUTCDate(dt.getUTCDate() - 1);
  return dt.toISOString().split("T")[0];
}

/**
 * Get the current edition date in a user's timezone.
 * Before 5 AM → yesterday's date. 5 AM onward → today's date.
 */
export function getEditionDate(
  timezone: string,
  now: Date = new Date()
): string {
  const { date, hour } = getDatePartsInTZ(timezone, now);
  return hour < EDITION_ROLLOVER_HOUR ? subtractOneDay(date) : date;
}

/**
 * Returns true if the current time is before the 5 AM edition cutoff
 * in the user's timezone (i.e. today's edition hasn't been built yet).
 */
export function isBeforeEditionCutoff(
  timezone: string,
  now: Date = new Date()
): boolean {
  const { hour } = getDatePartsInTZ(timezone, now);
  return hour < EDITION_ROLLOVER_HOUR;
}

/**
 * Returns true if the current time is before the user's scheduled
 * delivery time in their timezone.
 */
export function isBeforeDeliveryTime(
  deliveryTime: string,
  timezone: string,
  now: Date = new Date()
): boolean {
  const { hour, minute } = getDatePartsInTZ(timezone, now);
  const [dh, dm] = deliveryTime.split(":").map(Number);
  return hour < dh || (hour === dh && minute < dm);
}

/** Get current hour and minute in a timezone. */
export function getUserLocalHourMinute(
  timezone: string,
  now: Date = new Date()
): { hour: number; minute: number } {
  const { hour, minute } = getDatePartsInTZ(timezone, now);
  return { hour, minute };
}
