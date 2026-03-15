import type { Device } from "@/types";

export const DEVICES: { value: Device; label: string; description: string }[] =
  [
    {
      value: "kindle",
      label: "Kindle",
      description:
        "Amazon's e-reader. Delivery via Send-to-Kindle email, download, or wireless sync.",
    },
    {
      value: "kobo",
      label: "Kobo",
      description:
        "Rakuten Kobo e-reader. Delivery via Google Drive, download, or wireless sync.",
    },
    {
      value: "remarkable",
      label: "reMarkable",
      description:
        "reMarkable paper tablet. Delivery via email, Google Drive, download, or wireless sync.",
    },
    {
      value: "other",
      label: "Other",
      description:
        "Any other e-reader or tablet. Delivery via email, Google Drive, or download.",
    },
  ];

/** Default Google Drive folder name per device. */
export function defaultDriveFolderForDevice(device: Device | null): string {
  return device === "kobo" ? "Rakuten Kobo" : "Paper Boy News";
}

export const TIMEZONES = [
  { value: "Pacific/Honolulu", label: "Hawaii (HST)" },
  { value: "America/Anchorage", label: "Alaska (AKST)" },
  { value: "America/Los_Angeles", label: "US Pacific (PST)" },
  { value: "America/Denver", label: "US Mountain (MST)" },
  { value: "America/Chicago", label: "US Central (CST)" },
  { value: "America/New_York", label: "US Eastern (EST)" },
  { value: "America/Sao_Paulo", label: "Brazil (BRT)" },
  { value: "Atlantic/Reykjavik", label: "Iceland (GMT)" },
  { value: "Europe/London", label: "UK (GMT/BST)" },
  { value: "Europe/Paris", label: "Central Europe (CET)" },
  { value: "Europe/Helsinki", label: "Eastern Europe (EET)" },
  { value: "Asia/Dubai", label: "Gulf (GST)" },
  { value: "Asia/Kolkata", label: "India (IST)" },
  { value: "Asia/Shanghai", label: "China (CST)" },
  { value: "Asia/Tokyo", label: "Japan (JST)" },
  { value: "Australia/Sydney", label: "Australia Eastern (AEST)" },
  { value: "Pacific/Auckland", label: "New Zealand (NZST)" },
];

export const DELIVERY_TIMES = [
  { value: "05:00", label: "5:00 AM" },
  { value: "05:30", label: "5:30 AM" },
  { value: "06:00", label: "6:00 AM" },
  { value: "06:30", label: "6:30 AM" },
  { value: "07:00", label: "7:00 AM" },
  { value: "07:30", label: "7:30 AM" },
  { value: "08:00", label: "8:00 AM" },
  { value: "08:30", label: "8:30 AM" },
  { value: "09:00", label: "9:00 AM" },
  { value: "09:30", label: "9:30 AM" },
  { value: "10:00", label: "10:00 AM" },
  { value: "10:30", label: "10:30 AM" },
  { value: "11:00", label: "11:00 AM" },
  { value: "11:30", label: "11:30 AM" },
  { value: "12:00", label: "12:00 PM" },
  { value: "12:30", label: "12:30 PM" },
  { value: "13:00", label: "1:00 PM" },
  { value: "13:30", label: "1:30 PM" },
  { value: "14:00", label: "2:00 PM" },
  { value: "14:30", label: "2:30 PM" },
  { value: "15:00", label: "3:00 PM" },
  { value: "15:30", label: "3:30 PM" },
  { value: "16:00", label: "4:00 PM" },
  { value: "16:30", label: "4:30 PM" },
  { value: "17:00", label: "5:00 PM" },
  { value: "17:30", label: "5:30 PM" },
  { value: "18:00", label: "6:00 PM" },
  { value: "18:30", label: "6:30 PM" },
  { value: "19:00", label: "7:00 PM" },
  { value: "19:30", label: "7:30 PM" },
  { value: "20:00", label: "8:00 PM" },
  { value: "20:30", label: "8:30 PM" },
  { value: "21:00", label: "9:00 PM" },
  { value: "21:30", label: "9:30 PM" },
  { value: "22:00", label: "10:00 PM" },
  { value: "22:30", label: "10:30 PM" },
  { value: "23:00", label: "11:00 PM" },
  { value: "23:30", label: "11:30 PM" },
];

/** Map legacy timezone values (US/Eastern etc.) to IANA equivalents. */
export const LEGACY_TIMEZONE_MAP: Record<string, string> = {
  "US/Eastern": "America/New_York",
  "US/Central": "America/Chicago",
  "US/Pacific": "America/Los_Angeles",
  "US/Mountain": "America/Denver",
  "US/Hawaii": "Pacific/Honolulu",
  "US/Alaska": "America/Anchorage",
  UTC: "Atlantic/Reykjavik",
};

/** Normalize a timezone value, mapping legacy aliases to IANA names. */
export function normalizeTimezone(tz: string): string {
  return LEGACY_TIMEZONE_MAP[tz] ?? tz;
}

export const EDITION_ROLLOVER_HOUR = 5;

export const BUILD_MESSAGES = [
  "Setting the type...",
  "Pulling from the wire...",
  "Running the press...",
  "Folding and bundling...",
  "Out for delivery...",
];

export const BUILD_MESSAGES_ASYNC = [
  "Setting the type...",
  "Pulling from the wire...",
  "Running the press...",
  "Folding and bundling...",
  "Inking the pages...",
  "Paper Boy Russell is loading the truck...",
  "Driver Goudy has departed the loading dock...",
  "The truck has a flat on 5th Avenue. Spare is being fitted.",
  "Paper Boy Gibson took a wrong turn at the bridge. Doubling back.",
  "Replacement boy Alpert called in from Newark...",
  "The bridge is up. Driver Goudy is waiting.",
  "Paper Boy Sam dropped a stack in a puddle. Reprinting.",
  "A second truck has been dispatched...",
  "Driver Goudy's truck won't start. Paper Boy Russell is pushing.",
  "Paper Boy Gibson's bag strap snapped. Fashioning a replacement.",
  "The morning fog has grounded the ferry. Rerouting overland.",
  "Paper Boy Russell missed the 6 AM trolley. Running.",
  "The drawbridge operator is on his lunch break. Standing by.",
  "Driver Goudy took a detour through Philadelphia. Recalculating.",
  "Paper Boy Alpert's bicycle has a bent wheel. Mechanic en route.",
];
