"use client";

import { useEffect, useState } from "react";
import { toast } from "sonner";
import { CircleCheckIcon } from "lucide-react";

const TOAST_DURATION = 3000;
const TICK_INTERVAL = 30;

interface SaveToastProps {
  id: string | number;
  message: string;
  onUndo?: () => void;
}

export function SaveToast({ id, message, onUndo }: SaveToastProps) {
  const [elapsed, setElapsed] = useState(0);

  useEffect(() => {
    const interval = setInterval(() => {
      setElapsed((prev) => {
        if (prev >= TOAST_DURATION) {
          clearInterval(interval);
          return prev;
        }
        return prev + TICK_INTERVAL;
      });
    }, TICK_INTERVAL);
    return () => clearInterval(interval);
  }, []);

  const progress = Math.min(elapsed / TOAST_DURATION, 1);

  return (
    <div className="save-toast relative w-[var(--width)] overflow-hidden border border-[#4a9e6a] bg-[#5bba7c] px-4 py-3 shadow-lg">
      {/* Halftone texture overlay */}
      <div
        className="pointer-events-none absolute inset-0 mix-blend-multiply opacity-40"
        style={{
          backgroundImage:
            "radial-gradient(circle, rgba(0, 40, 10, 0.25) 30%, transparent 30%)",
          backgroundSize: "5px 5px",
        }}
      />

      {/* Content */}
      <div className="relative z-10 flex items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <CircleCheckIcon className="h-4 w-4 shrink-0 text-white/90" />
          <span className="font-[var(--font-headline)] text-sm font-bold text-white">
            {message}
          </span>
        </div>
        {onUndo && (
          <button
            onClick={() => {
              onUndo();
              toast.dismiss(id);
            }}
            className="shrink-0 font-[var(--font-mono)] text-xs font-bold text-white/90 underline underline-offset-2 transition-colors hover:text-white"
          >
            Undo
          </button>
        )}
      </div>

      {/* Progress bar — counts down to show remaining undo time */}
      <div className="absolute inset-x-0 bottom-0 h-[3px] bg-black/10">
        <div
          className="h-full bg-white/50 transition-none"
          style={{ width: `${(1 - progress) * 100}%` }}
        />
      </div>
    </div>
  );
}

/** Show a save toast with optional undo. Replaces toast.success() for settings saves. */
export function showSaveToast(message: string, onUndo?: () => void) {
  toast.custom(
    (id) => <SaveToast id={id} message={message} onUndo={onUndo} />,
    { duration: TOAST_DURATION }
  );
}
