"use client";

import { cn } from "@/lib/utils";
import type { Device } from "@/types";
import { DeviceIcon } from "./device-icons";

interface DeviceCardProps {
  device: Device;
  label: string;
  selected: boolean;
  onClick: () => void;
}

export function DeviceCard({
  device,
  label,
  selected,
  onClick,
}: DeviceCardProps) {
  return (
    <button
      onClick={onClick}
      className={cn(
        "flex w-full flex-col items-center gap-3 rounded-sm border-2 bg-white p-6 transition-all",
        selected
          ? "border-edition-red shadow-sm"
          : "border-rule-gray hover:border-caption"
      )}
    >
      <DeviceIcon device={device} className="h-20 w-16 text-ink" />
      <span className="font-body text-sm font-semibold text-ink">{label}</span>
    </button>
  );
}
