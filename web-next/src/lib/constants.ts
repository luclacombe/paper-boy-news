import type { Device } from "@/types";

export const DEVICES: { value: Device; label: string; description: string }[] =
  [
    {
      value: "kindle",
      label: "Kindle",
      description: "Amazon's e-reader. Delivery via Send-to-Kindle email.",
    },
    {
      value: "kobo",
      label: "Kobo",
      description:
        "Rakuten Kobo e-reader. Delivery via Google Drive auto-sync.",
    },
    {
      value: "remarkable",
      label: "reMarkable",
      description: "reMarkable paper tablet. Download and transfer via USB/app.",
    },
    {
      value: "other",
      label: "Other",
      description: "Any other e-reader or reading app. Download EPUB directly.",
    },
  ];

export const TIMEZONES = [
  { value: "UTC", label: "UTC" },
  { value: "US/Eastern", label: "US Eastern" },
  { value: "US/Central", label: "US Central" },
  { value: "US/Pacific", label: "US Pacific" },
  { value: "Europe/London", label: "Europe/London" },
  { value: "Europe/Paris", label: "Europe/Paris" },
];

export const DELIVERY_TIMES = [
  { value: "05:00", label: "5:00 AM" },
  { value: "05:30", label: "5:30 AM" },
  { value: "06:00", label: "6:00 AM" },
  { value: "06:30", label: "6:30 AM" },
  { value: "07:00", label: "7:00 AM" },
  { value: "07:30", label: "7:30 AM" },
  { value: "08:00", label: "8:00 AM" },
];

export const EDITION_ROLLOVER_HOUR = 5;

export const BUILD_MESSAGES = [
  "Setting the type...",
  "Pulling from the wire...",
  "Running the press...",
  "Folding and bundling...",
  "Out for delivery...",
];
