import { cn } from "@/lib/utils";

interface MarginDecorationProps {
  side: "left" | "right";
}

export function MarginDecoration({ side }: MarginDecorationProps) {
  return (
    <div className="sticky top-0 flex h-[calc(100vh-6rem)] items-center justify-center">
      <div
        className={cn(
          "flex flex-col items-center gap-8 py-14 opacity-30",
          side === "left"
            ? "border-r border-rule-gray pr-4"
            : "border-l border-rule-gray pl-4"
        )}
      >
        <span className="font-display text-xs tracking-[0.3em] text-rule-gray [writing-mode:vertical-rl]">
          PAPER BOY
        </span>
        <span className="font-display text-lg text-rule-gray">&sect;</span>
        <span className="font-mono text-[9px] tracking-widest text-rule-gray [writing-mode:vertical-rl]">
          MORNING EDITION
        </span>
        <span className="font-display text-lg text-rule-gray">&sect;</span>
        <span className="font-mono text-[8px] tracking-widest text-rule-gray [writing-mode:vertical-rl]">
          EST. 2025
        </span>
      </div>
    </div>
  );
}
