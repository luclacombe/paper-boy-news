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
        "newsprint-card w-full overflow-hidden border-2 bg-card p-4 text-left transition-all duration-150 hover:scale-[1.01] hover:-translate-y-px active:scale-[0.99]",
        selected
          ? "border-edition-red shadow-sm"
          : "border-rule-gray hover:border-caption"
      )}
    >
      <h3 className="font-headline text-sm font-bold text-ink">{name}</h3>
      <p className="mt-1 font-body text-xs italic text-caption">
        {description}
      </p>
    </button>
  );
}
