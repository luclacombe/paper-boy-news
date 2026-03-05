"use client";

import { cn } from "@/lib/utils";
import { motion } from "motion/react";

interface BundleCardProps {
  name: string;
  description: string;
  selected: boolean;
  onClick: () => void;
}

export function BundleCard({
  name,
  description,
  selected,
  onClick,
}: BundleCardProps) {
  return (
    <motion.button
      onClick={onClick}
      whileHover={{ scale: 1.01, y: -1 }}
      whileTap={{ scale: 0.99 }}
      transition={{ duration: 0.15 }}
      className={cn(
        "newsprint-card w-full overflow-hidden border-2 bg-card p-4 text-left transition-colors",
        selected
          ? "border-edition-red shadow-sm"
          : "border-rule-gray hover:border-caption"
      )}
    >
      <h3 className="font-headline text-sm font-bold text-ink">{name}</h3>
      <p className="mt-1 font-body text-xs italic text-caption">
        {description}
      </p>
    </motion.button>
  );
}
