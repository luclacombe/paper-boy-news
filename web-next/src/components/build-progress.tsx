"use client";

import { Progress } from "@/components/ui/progress";
import { BUILD_MESSAGES } from "@/lib/constants";

interface BuildProgressProps {
  step: number; // 0-4 (index into BUILD_MESSAGES)
  totalSteps?: number;
}

export function BuildProgress({ step, totalSteps = 5 }: BuildProgressProps) {
  const progress = ((step + 1) / totalSteps) * 100;
  const message = BUILD_MESSAGES[step] ?? BUILD_MESSAGES[0];

  return (
    <div className="space-y-3 py-4">
      <Progress value={progress} className="h-2" />
      <p className="text-center font-headline text-sm italic text-caption">
        {message}
      </p>
    </div>
  );
}
