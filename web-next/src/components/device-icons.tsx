import {
  Tablet,
  BookOpen,
  Smartphone,
  Monitor,
} from "lucide-react";
import type { Device } from "@/types";
import { cn } from "@/lib/utils";

interface DeviceIconProps {
  device: Device;
  className?: string;
}

/**
 * Simple device icons using Lucide.
 * The Streamlit version uses base64 PNGs — these will be replaced
 * with proper illustrations during the UI expansion phase.
 */
export function DeviceIcon({ device, className }: DeviceIconProps) {
  const iconClass = cn("stroke-[1.5]", className);

  switch (device) {
    case "kindle":
      return <Tablet className={iconClass} />;
    case "kobo":
      return <BookOpen className={iconClass} />;
    case "remarkable":
      return <Smartphone className={iconClass} />;
    case "other":
      return <Monitor className={iconClass} />;
  }
}
