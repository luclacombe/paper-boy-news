import Image from "next/image";
import type { Device } from "@/types";
import { cn } from "@/lib/utils";

interface DeviceIconProps {
  device: Device;
  className?: string;
}

const DEVICE_IMAGES: Record<Device, string> = {
  kindle: "/devices/kindle.png",
  kobo: "/devices/kobo.png",
  remarkable: "/devices/remarkable.png",
  other: "/devices/other.png",
};

export function DeviceIcon({ device, className }: DeviceIconProps) {
  return (
    <Image
      src={DEVICE_IMAGES[device]}
      alt={device}
      width={90}
      height={120}
      className={cn("newsprint-image", className)}
    />
  );
}
