"use client";

import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { DELIVERY_TIMES, TIMEZONES, EDITION_ROLLOVER_HOUR } from "@/lib/constants";

export interface ScheduleValues {
  deliveryTime: string;
  timezone: string;
}

interface ScheduleSectionProps {
  values: ScheduleValues;
  onChange: (values: ScheduleValues) => void;
}

export function ScheduleSection({ values, onChange }: ScheduleSectionProps) {
  function update(patch: Partial<ScheduleValues>) {
    onChange({ ...values, ...patch });
  }

  return (
    <div className="space-y-4">
      <div className="grid gap-4 sm:grid-cols-2">
        <div className="space-y-1.5">
          <Label className="font-headline text-sm text-ink">
            Delivery time
          </Label>
          <Select
            value={values.deliveryTime}
            onValueChange={(v) => update({ deliveryTime: v })}
          >
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {DELIVERY_TIMES.map((t) => (
                <SelectItem key={t.value} value={t.value}>
                  {t.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div className="space-y-1.5">
          <Label className="font-headline text-sm text-ink">Timezone</Label>
          <Select
            value={values.timezone}
            onValueChange={(v) => update({ timezone: v })}
          >
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {TIMEZONES.map((tz) => (
                <SelectItem key={tz.value} value={tz.value}>
                  {tz.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </div>
      <p className="font-body text-xs text-caption">
        Your paper is built at {EDITION_ROLLOVER_HOUR}:00 AM and delivered at
        your scheduled time.
      </p>
    </div>
  );
}
