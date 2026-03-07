import { cn } from "@/lib/utils";
import { Check, Circle, X, Diamond } from "lucide-react";

type Status = "delivered" | "building" | "failed" | "empty";

const STATUS_CONFIG: Record<
  Status,
  { icon: typeof Check; borderColor: string; bgColor: string }
> = {
  delivered: {
    icon: Check,
    borderColor: "border-l-delivered",
    bgColor: "bg-delivered/5",
  },
  building: {
    icon: Circle,
    borderColor: "border-l-building",
    bgColor: "bg-building/5",
  },
  failed: {
    icon: X,
    borderColor: "border-l-failed",
    bgColor: "bg-failed/5",
  },
  empty: {
    icon: Diamond,
    borderColor: "border-l-rule-gray",
    bgColor: "bg-warm-gray/30",
  },
};

interface StatusBannerProps {
  status: Status;
  message: string;
  detail?: string;
}

export function StatusBanner({ status, message, detail }: StatusBannerProps) {
  const config = STATUS_CONFIG[status];
  const Icon = config.icon;

  return (
    <div
      className={cn(
        "rounded-sm border-l-4 p-4 text-center",
        config.borderColor,
        config.bgColor
      )}
    >
      <div className="flex items-center justify-center gap-2">
        <Icon className="h-4 w-4" />
        <span className="font-body text-sm font-semibold text-ink">
          {message}
        </span>
      </div>
      {detail && (
        <p className="mt-1 font-mono text-xs text-caption">{detail}</p>
      )}
    </div>
  );
}
