import { Button } from "@/components/ui/button";
import { Trash2 } from "lucide-react";

interface SourceCardProps {
  name: string;
  onRemove?: () => void;
}

export function SourceCard({ name, onRemove }: SourceCardProps) {
  return (
    <div className="flex items-center justify-between border-b border-rule-gray py-3">
      <span className="font-body text-sm font-semibold text-ink">{name}</span>
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
