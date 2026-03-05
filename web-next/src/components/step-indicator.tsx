import { cn } from "@/lib/utils";

interface StepIndicatorProps {
  currentStep: number;
  totalSteps: number;
  maxStepVisited?: number;
  onStepClick?: (step: number) => void;
}

export function StepIndicator({
  currentStep,
  totalSteps,
  maxStepVisited = currentStep,
  onStepClick,
}: StepIndicatorProps) {
  return (
    <div className="flex items-center justify-center font-mono text-xs tracking-widest text-caption">
      <span className="text-rule-gray" aria-hidden="true">
        &mdash;
      </span>
      {Array.from({ length: totalSteps }, (_, i) => {
        const step = i + 1;
        const isActive = step === currentStep;
        const isPast = step < currentStep;
        const isClickable =
          onStepClick && !isActive && step <= maxStepVisited;
        return (
          <span key={step} className="flex items-center">
            <button
              type="button"
              disabled={!isClickable}
              onClick={() => isClickable && onStepClick(step)}
              className={cn(
                "mx-1 inline-block min-w-[1.5em] text-center",
                isActive && "font-bold text-ink",
                isPast && "text-caption",
                !isActive && !isPast && "text-rule-gray",
                isClickable &&
                  "cursor-pointer underline decoration-rule-gray underline-offset-2 hover:text-ink"
              )}
              aria-label={`Step ${step}${isActive ? " (current)" : ""}`}
            >
              {isActive ? `[ ${step} ]` : step}
            </button>
            {step < totalSteps && (
              <span className="text-rule-gray" aria-hidden="true">
                &middot;
              </span>
            )}
          </span>
        );
      })}
      <span className="text-rule-gray" aria-hidden="true">
        &mdash;
      </span>
    </div>
  );
}
