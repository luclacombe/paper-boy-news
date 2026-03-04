"use client";

import { cn } from "@/lib/utils";

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
    <button
      onClick={onClick}
      className={cn(
        "w-full rounded-sm border-2 bg-white p-4 text-left transition-all",
        selected
          ? "border-edition-red shadow-sm"
          : "border-rule-gray hover:border-caption"
      )}
    >
      <h3 className="font-headline text-sm font-bold text-ink">{name}</h3>
      <p className="mt-1 font-body text-xs text-caption">{description}</p>
    </button>
  );
}
