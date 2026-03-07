import {
  DEVICES,
  DELIVERY_TIMES,
  TIMEZONES,
  EDITION_ROLLOVER_HOUR,
} from "@/lib/constants";
import type { UserConfig } from "@/types";

const FRIENDLY_TZ: Record<string, string> = {
  UTC: "UTC",
  "US/Eastern": "Eastern",
  "US/Central": "Central",
  "US/Pacific": "Pacific",
  "America/New_York": "Eastern",
  "America/Chicago": "Central",
  "America/Los_Angeles": "Pacific",
  "Europe/London": "London",
  "Europe/Paris": "Paris",
};

export function formatTimezone(timezone: string): string {
  if (FRIENDLY_TZ[timezone]) return FRIENDLY_TZ[timezone];
  const tzOption = TIMEZONES.find((t) => t.value === timezone);
  if (tzOption) return tzOption.label;
  return timezone.includes("/")
    ? timezone.split("/").pop()!.replace(/_/g, " ")
    : timezone;
}

export function formatTimeAndZone(
  deliveryTime: string,
  timezone: string
): string {
  const timeOption = DELIVERY_TIMES.find((t) => t.value === deliveryTime);
  const timeLabel = timeOption?.label ?? deliveryTime;
  const tzLabel = formatTimezone(timezone);
  return `${timeLabel} ${tzLabel}`;
}

function formatRolloverTime(timezone: string): string {
  const tzLabel = formatTimezone(timezone);
  const hour = EDITION_ROLLOVER_HOUR;
  return `${hour}:00 AM ${tzLabel}`;
}

/** Past tense — what happened with the latest edition */
export function getDeliveryPastTense(config: UserConfig): string {
  const deviceLabel =
    DEVICES.find((d) => d.value === config.device)?.label ?? config.device;

  if (config.deliveryMethod === "google_drive") {
    return `delivered to your ${deviceLabel} via Google Drive`;
  }
  if (config.deliveryMethod === "email") {
    return `emailed to your ${deviceLabel}`;
  }
  return "ready to download";
}

/** Next edition sentence for footer — "Your next edition will be delivered tomorrow at 7:00 AM Eastern" */
export function getNextDeliverySentence(config: UserConfig): string {
  const deviceLabel =
    DEVICES.find((d) => d.value === config.device)?.label ?? config.device;
  const time = formatTimeAndZone(config.deliveryTime, config.timezone);

  if (config.deliveryMethod === "google_drive") {
    return `Your next edition will be delivered to your ${deviceLabel} tomorrow at ${time}`;
  }
  if (config.deliveryMethod === "email") {
    return `Your next edition will be emailed to your ${deviceLabel} tomorrow at ${time}`;
  }
  return `Your next edition will be ready for download tomorrow at ${time}`;
}

/** Pre-build sentence — shown before 5 AM when the edition doesn't exist yet */
export function getPreBuildSentence(
  config: UserConfig,
  isFirst: boolean
): string {
  const deviceLabel =
    DEVICES.find((d) => d.value === config.device)?.label ?? config.device;
  const rollover = formatRolloverTime(config.timezone);
  const delivery = formatTimeAndZone(config.deliveryTime, config.timezone);

  if (isFirst) {
    if (config.deliveryMethod === "google_drive") {
      return `Your custom paper will be delivered to your ${deviceLabel} via Google Drive at ${delivery}, every morning.`;
    }
    if (config.deliveryMethod === "email") {
      return `Your custom paper will be emailed to your ${deviceLabel} at ${delivery}, every morning.`;
    }
    return `Your custom paper will be ready for download here at ${delivery}, every morning.`;
  }

  if (config.deliveryMethod === "google_drive") {
    return `Tomorrow\u2019s paper will be ready at ${rollover}. Yours is scheduled for delivery at ${delivery}.`;
  }
  if (config.deliveryMethod === "email") {
    return `Tomorrow\u2019s paper will be ready at ${rollover}. Yours is scheduled for delivery at ${delivery}.`;
  }
  return `Tomorrow\u2019s paper will be ready at ${rollover}. Yours is scheduled for download at ${delivery}.`;
}

/** Ready sentence — shown after 5 AM when edition is available but not yet delivered */
export function getReadySentence(config: UserConfig): string {
  const time = formatTimeAndZone(config.deliveryTime, config.timezone);
  if (config.deliveryMethod === "local") {
    return `Your paper is also scheduled for download at ${time} tomorrow.`;
  }
  return `Your paper is also scheduled for delivery at ${time} tomorrow.`;
}

/** "Get it now" description — what will happen if they trigger early */
export function getEarlyDeliveryDescription(config: UserConfig): string {
  const deviceLabel =
    DEVICES.find((d) => d.value === config.device)?.label ?? config.device;

  if (config.deliveryMethod === "google_drive") {
    return `It will be delivered to your ${deviceLabel} via Google Drive`;
  }
  if (config.deliveryMethod === "email") {
    return `It will be emailed to your ${deviceLabel}`;
  }
  return "It will be ready to download right away";
}

/** Scheduled time sentence — "scheduled for 6:00 AM Eastern" */
export function getScheduledTimeSentence(config: UserConfig): string {
  const time = formatTimeAndZone(config.deliveryTime, config.timezone);
  return `scheduled for ${time}`;
}
