import { cn } from "@/lib/utils";

interface StepIndicatorProps {
  currentStep: number;
  totalSteps: number;
}

export function StepIndicator({ currentStep, totalSteps }: StepIndicatorProps) {
  return (
    <div className="flex items-center justify-center gap-2">
      {Array.from({ length: totalSteps }, (_, i) => {
        const step = i + 1;
        return (
          <div
            key={step}
            className={cn(
              "h-2.5 w-2.5 rounded-full transition-colors",
              step === currentStep
                ? "bg-edition-red"
                : step < currentStep
                  ? "bg-ink"
                  : "bg-rule-gray"
            )}
          />
        );
      })}
    </div>
  );
}
