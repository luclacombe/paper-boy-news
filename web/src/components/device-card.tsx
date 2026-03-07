"use client";

import { cn } from "@/lib/utils";
import { motion } from "motion/react";
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
    <motion.button
      onClick={onClick}
      whileHover={{ scale: 1.02 }}
      whileTap={{ scale: 0.98 }}
      transition={{ duration: 0.15 }}
      className={cn(
        "newsprint-card flex w-full flex-col items-center gap-3 overflow-hidden border-2 bg-card p-6 transition-colors",
        selected
          ? "border-edition-red shadow-md shadow-edition-red/20"
          : "border-rule-gray hover:border-caption"
      )}
    >
      <DeviceIcon device={device} className="h-[60px] w-[45px]" />
      <span className="small-caps font-headline text-sm font-bold text-ink">
        {label}
      </span>
    </motion.button>
  );
}
