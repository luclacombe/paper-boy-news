"use client";

import { Progress } from "@/components/ui/progress";
import { BUILD_MESSAGES, BUILD_MESSAGES_ASYNC } from "@/lib/constants";

interface BuildProgressProps {
  step: number;
  async?: boolean;
}

export function BuildProgress({ step, async: isAsync }: BuildProgressProps) {
  const messages = isAsync ? BUILD_MESSAGES_ASYNC : BUILD_MESSAGES;
  const totalSteps = messages.length;
  const clampedStep = Math.min(step, totalSteps - 1);
  const progress = ((clampedStep + 1) / totalSteps) * 100;
  const message = messages[clampedStep] ?? messages[0];

  return (
    <div className="space-y-3 py-4">
      <Progress value={progress} className="h-2" />
      <p className="text-center font-headline text-sm italic text-caption">
        {message}
      </p>
    </div>
  );
}
