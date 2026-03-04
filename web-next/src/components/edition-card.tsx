import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Download } from "lucide-react";

interface EditionCardProps {
  date: string;
  editionNumber: number;
  articleCount: number;
  sourceCount: number;
  fileSize: string;
  status: "delivered" | "failed" | "building";
  deliveryMethod?: string;
  errorMessage?: string | null;
  onDownload?: () => void;
}

const STATUS_BADGE = {
  delivered: {
    label: "Delivered",
    className: "border-delivered/30 bg-delivered/5 text-delivered",
  },
  failed: {
    label: "Failed",
    className: "border-failed/30 bg-failed/5 text-failed",
  },
  building: {
    label: "Building...",
    className: "border-building/30 bg-building/5 text-building",
  },
};

const METHOD_LABELS: Record<string, string> = {
  google_drive: "via Google Drive",
  email: "via Email",
  gmail_api: "via Gmail",
  local: "Downloaded",
};

export function EditionCard({
  date,
  editionNumber,
  articleCount,
  sourceCount,
  fileSize,
  status,
  deliveryMethod,
  errorMessage,
  onDownload,
}: EditionCardProps) {
  const badge = STATUS_BADGE[status];

  return (
    <div className="border-b border-rule-gray py-4">
      <div className="flex items-start justify-between">
        <div>
          <div className="flex items-center gap-2">
            <span className="font-headline text-sm font-bold text-ink">
              {date}
            </span>
            <Badge variant="outline" className={badge.className}>
              {badge.label}
            </Badge>
          </div>
          <p className="mt-1 font-mono text-xs text-caption">
            Edition #{editionNumber} · {articleCount} articles · {sourceCount}{" "}
            sources · {fileSize}
          </p>
          {deliveryMethod && (
            <p className="font-body text-xs text-caption">
              {METHOD_LABELS[deliveryMethod] ?? deliveryMethod}
            </p>
          )}
          {errorMessage && (
            <p className="mt-1 font-body text-xs text-edition-red">
              {errorMessage}
            </p>
          )}
        </div>
        {status === "delivered" && onDownload && (
          <Button
            variant="ghost"
            size="icon"
            onClick={onDownload}
            className="h-8 w-8 text-caption hover:text-ink"
          >
            <Download className="h-4 w-4" />
          </Button>
        )}
      </div>
    </div>
  );
}
