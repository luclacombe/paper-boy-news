"use client";

import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Checkbox } from "@/components/ui/checkbox";
import { cn } from "@/lib/utils";
import { READING_TIME_OPTIONS, readingTimeToArticleBudget } from "@/lib/reading-time";

export interface PaperValues {
  title: string;
  readingTime: number;
  includeImages: boolean;
}

interface PaperSectionProps {
  values: PaperValues;
  onChange: (values: PaperValues) => void;
}

export function PaperSection({ values, onChange }: PaperSectionProps) {
  function update(patch: Partial<PaperValues>) {
    onChange({ ...values, ...patch });
  }

  return (
    <div className="space-y-4">
      {/* Newspaper title */}
      <div className="space-y-1.5">
        <Label className="font-headline text-sm text-ink">
          Newspaper title
        </Label>
        <Input
          value={values.title}
          onChange={(e) => update({ title: e.target.value })}
          placeholder="The Morning Paper"
          style={{ fontVariantNumeric: "lining-nums" }}
        />
        <p className="font-body text-xs text-caption">
          Appears on your EPUB cover and in the masthead.
        </p>
      </div>

      {/* Reading time */}
      <div className="space-y-1.5">
        <Label className="font-headline text-sm text-ink">Reading time</Label>
        <div className="flex border border-rule-gray">
          {READING_TIME_OPTIONS.map((minutes) => {
            const isSelected = values.readingTime === minutes;
            return (
              <button
                key={minutes}
                type="button"
                onClick={() => update({ readingTime: minutes })}
                className={cn(
                  "flex-1 py-2.5 font-mono text-xs transition-colors",
                  "border-r border-rule-gray last:border-r-0",
                  isSelected
                    ? "letterpress bg-ink font-bold text-newsprint"
                    : "bg-card text-caption hover:bg-warm-gray hover:text-ink"
                )}
              >
                {minutes}m
              </button>
            );
          })}
        </div>
        <p className="font-mono text-xs text-caption">
          ~{readingTimeToArticleBudget(values.readingTime)} articles total
        </p>
      </div>

      {/* Include images */}
      <label className="flex items-center gap-3">
        <Checkbox
          checked={values.includeImages}
          onCheckedChange={(checked) =>
            update({ includeImages: checked === true })
          }
        />
        <span className="font-body text-sm text-ink">
          Include images in articles
        </span>
      </label>
    </div>
  );
}
