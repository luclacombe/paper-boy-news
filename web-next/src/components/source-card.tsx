import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Trash2 } from "lucide-react";

interface SourceCardProps {
  name: string;
  url: string;
  articleCount?: number;
  status?: "active" | "warning";
  onRemove?: () => void;
}

export function SourceCard({
  name,
  url,
  articleCount,
  status = "active",
  onRemove,
}: SourceCardProps) {
  return (
    <div className="flex items-center justify-between border-b border-rule-gray py-3">
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <span className="font-body text-sm font-semibold text-ink">
            {name}
          </span>
          <Badge
            variant="outline"
            className={
              status === "active"
                ? "border-delivered/30 bg-delivered/5 text-delivered"
                : "border-building/30 bg-building/5 text-building"
            }
          >
            {status === "active" ? "Active" : "Warning"}
          </Badge>
        </div>
        <p className="truncate font-mono text-xs text-caption">{url}</p>
        {articleCount !== undefined && (
          <p className="font-mono text-xs text-caption">
            {articleCount} article{articleCount === 1 ? "" : "s"}
          </p>
        )}
      </div>
      {onRemove && (
        <Button
          variant="ghost"
          size="icon"
          onClick={onRemove}
          className="ml-2 h-8 w-8 text-caption hover:text-edition-red"
        >
          <Trash2 className="h-4 w-4" />
        </Button>
      )}
    </div>
  );
}
