"use client";

import { BUILD_MESSAGES, BUILD_MESSAGES_ASYNC } from "@/lib/constants";

interface BuildProgressProps {
  step: number;
  async?: boolean;
}

export function BuildProgress({ step, async: isAsync }: BuildProgressProps) {
  const messages = isAsync ? BUILD_MESSAGES_ASYNC : BUILD_MESSAGES;
  const totalSteps = messages.length;
  const clampedStep = Math.min(step, totalSteps - 1);
  // Logarithmic ease: fills fast early, slows down, caps at ~95%
  const linearProgress = (clampedStep + 1) / totalSteps;
  const progress = Math.min(95, Math.log(1 + linearProgress * 9) / Math.log(10) * 100);
  const message = messages[clampedStep] ?? messages[0];

  return (
    <div className="space-y-3 py-4">
      <div className="relative h-4 w-full overflow-hidden rounded-full bg-ink/10">
        <div
          className="relative h-full bg-ink transition-all duration-700 ease-out"
          style={{ width: `${progress}%` }}
        >
          {/* Shimmer overlay (inside fill — only covers filled portion) */}
          <div
            className="pointer-events-none absolute inset-0 animate-shimmer"
            style={{
              background:
                "linear-gradient(90deg, transparent 0%, rgba(255,255,255,0.3) 50%, transparent 100%)",
              backgroundSize: "200% 100%",
            }}
          />
        </div>
        {/* Halftone dot overlay */}
        <div
          className="pointer-events-none absolute inset-0 mix-blend-multiply opacity-50"
          style={{
            backgroundImage:
              "radial-gradient(circle, rgba(80, 60, 30, 0.3) 30%, transparent 30%)",
            backgroundSize: "5px 5px",
          }}
        />
      </div>
      <p className="text-center font-headline text-sm italic text-caption">
        {message}
      </p>
    </div>
  );
}
