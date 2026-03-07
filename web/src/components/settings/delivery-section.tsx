"use client";

import { useState, useTransition } from "react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import {
  getGoogleAuthUrl,
  disconnectGoogle,
} from "@/actions/google-oauth";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import { cn } from "@/lib/utils";
import { DEVICES } from "@/lib/constants";
import type { Device, DeliveryMethod, EmailMethod } from "@/types";

export interface DeliveryValues {
  device: Device;
  deliveryMethod: DeliveryMethod;
  kindleEmail: string;
  googleDriveFolder: string;
  emailMethod: EmailMethod;
  emailSmtpHost: string;
  emailSmtpPort: string;
  emailSender: string;
  emailPassword: string;
}

interface DeliverySectionProps {
  values: DeliveryValues;
  onChange: (values: DeliveryValues) => void;
  hasDrive: boolean;
  hasGmail: boolean;
}

function getDeliveryMethodsForDevice(
  device: Device | null
): { value: DeliveryMethod; label: string; description: string }[] {
  switch (device) {
    case "kobo":
      return [
        {
          value: "google_drive",
          label: "Google Drive",
          description: "Auto-sync via Kobo's Google Drive integration",
        },
        {
          value: "local",
          label: "Download",
          description: "Download EPUB and transfer manually",
        },
      ];
    case "kindle":
      return [
        {
          value: "email",
          label: "Send-to-Kindle",
          description: "Deliver via email to your Kindle",
        },
        {
          value: "local",
          label: "Download",
          description: "Download EPUB and transfer via USB",
        },
      ];
    default:
      return [
        {
          value: "local",
          label: "Download",
          description: "Download EPUB and transfer to your device",
        },
        {
          value: "email",
          label: "Email",
          description: "Send EPUB to an email address",
        },
      ];
  }
}

export function DeliverySection({
  values,
  onChange,
  hasDrive,
  hasGmail,
}: DeliverySectionProps) {
  const router = useRouter();
  const [isPending, startTransition] = useTransition();
  const [smtpTesting, setSmtpTesting] = useState(false);

  const methods = getDeliveryMethodsForDevice(values.device);

  function update(patch: Partial<DeliveryValues>) {
    onChange({ ...values, ...patch });
  }

  function handleDeviceChange(d: Device) {
    const newMethods = getDeliveryMethodsForDevice(d);
    update({ device: d, deliveryMethod: newMethods[0].value });
  }

  async function handleGoogleConnect() {
    try {
      const url = await getGoogleAuthUrl();
      window.location.href = url;
    } catch {
      toast.error("Failed to start Google authorization");
    }
  }

  async function handleGoogleDisconnect() {
    startTransition(async () => {
      try {
        await disconnectGoogle();
        router.refresh();
        toast.success("Google account disconnected");
      } catch {
        toast.error("Failed to disconnect");
      }
    });
  }

  async function handleSmtpTest() {
    setSmtpTesting(true);
    try {
      const apiUrl = process.env.NEXT_PUBLIC_FASTAPI_URL;
      const res = await fetch(`${apiUrl}/smtp-test`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          smtp_host: values.emailSmtpHost,
          smtp_port: Number(values.emailSmtpPort) || 465,
          sender: values.emailSender,
          password: values.emailPassword,
        }),
      });
      const data = await res.json();
      if (data.success) {
        toast.success("SMTP connection successful");
      } else {
        toast.error(data.message ?? "SMTP test failed");
      }
    } catch {
      toast.error("SMTP test failed");
    } finally {
      setSmtpTesting(false);
    }
  }

  return (
    <div className="space-y-4">
      {/* Device — compact segmented control */}
      <div className="space-y-1.5">
        <Label className="font-headline text-sm text-ink">Device</Label>
        <div className="flex border border-rule-gray">
          {DEVICES.map((d) => {
            const isSelected = values.device === d.value;
            return (
              <button
                key={d.value}
                type="button"
                onClick={() => handleDeviceChange(d.value)}
                className={cn(
                  "flex-1 py-2.5 font-headline text-xs transition-colors",
                  "border-r border-rule-gray last:border-r-0",
                  isSelected
                    ? "letterpress bg-ink font-bold text-newsprint"
                    : "bg-card text-caption hover:bg-warm-gray hover:text-ink"
                )}
              >
                {d.label}
              </button>
            );
          })}
        </div>
      </div>

      {/* Delivery method */}
      <div className="space-y-1.5">
        <Label className="font-headline text-sm text-ink">
          How it&apos;s delivered
        </Label>
        <RadioGroup
          value={values.deliveryMethod}
          onValueChange={(v) => update({ deliveryMethod: v as DeliveryMethod })}
          className="space-y-2"
        >
          {methods.map((m) => (
            <label
              key={m.value}
              className="flex items-start gap-3 border border-rule-gray bg-card px-4 py-3 hover:border-caption"
            >
              <RadioGroupItem value={m.value} className="mt-0.5" />
              <div>
                <span className="font-headline text-sm font-bold text-ink">
                  {m.label}
                </span>
                <p className="font-body text-xs text-caption">
                  {m.description}
                </p>
              </div>
            </label>
          ))}
        </RadioGroup>
      </div>

      {/* Google Drive config */}
      {values.deliveryMethod === "google_drive" && (
        <div className="space-y-3">
          <div className="flex items-center gap-3">
            <span
              className={`inline-block h-2 w-2 rounded-full ${
                hasDrive ? "bg-delivered" : "bg-building"
              }`}
            />
            <span className="font-body text-sm text-ink">
              {hasDrive ? "Google Drive connected" : "Google Drive not connected"}
            </span>
          </div>
          {hasDrive ? (
            <Button
              variant="outline"
              size="sm"
              onClick={handleGoogleDisconnect}
              disabled={isPending}
            >
              Disconnect
            </Button>
          ) : (
            <Button
              size="sm"
              onClick={handleGoogleConnect}
              className="letterpress bg-ink text-newsprint hover:bg-ink/90"
            >
              Connect Google Drive
            </Button>
          )}
          <div className="space-y-1.5">
            <Label className="font-headline text-sm text-ink">
              Drive folder name
            </Label>
            <Input
              value={values.googleDriveFolder}
              onChange={(e) => update({ googleDriveFolder: e.target.value })}
              placeholder="Paper Boy"
            />
          </div>
        </div>
      )}

      {/* Email config */}
      {values.deliveryMethod === "email" && (
        <div className="space-y-3">
          {values.device === "kindle" && (
            <div className="space-y-1.5">
              <Label className="font-headline text-sm text-ink">
                Kindle email address
              </Label>
              <Input
                type="email"
                value={values.kindleEmail}
                onChange={(e) => update({ kindleEmail: e.target.value })}
                placeholder="your-kindle@kindle.com"
              />
            </div>
          )}

          <div className="space-y-1.5">
            <Label className="font-headline text-sm text-ink">Send via</Label>
            <RadioGroup
              value={values.emailMethod}
              onValueChange={(v) => update({ emailMethod: v as EmailMethod })}
              className="flex gap-4"
            >
              <label className="flex items-center gap-2">
                <RadioGroupItem value="gmail" />
                <span className="font-body text-sm text-ink">Gmail API</span>
              </label>
              <label className="flex items-center gap-2">
                <RadioGroupItem value="smtp" />
                <span className="font-body text-sm text-ink">SMTP</span>
              </label>
            </RadioGroup>
          </div>

          {values.emailMethod === "gmail" && (
            <div className="space-y-3">
              <div className="flex items-center gap-3">
                <span
                  className={`inline-block h-2 w-2 rounded-full ${
                    hasGmail ? "bg-delivered" : "bg-building"
                  }`}
                />
                <span className="font-body text-sm text-ink">
                  {hasGmail ? "Gmail connected" : "Gmail not connected"}
                </span>
              </div>
              {hasGmail ? (
                <Button
                  variant="outline"
                  size="sm"
                  onClick={handleGoogleDisconnect}
                  disabled={isPending}
                >
                  Disconnect
                </Button>
              ) : (
                <Button
                  size="sm"
                  onClick={handleGoogleConnect}
                  className="letterpress bg-ink text-newsprint hover:bg-ink/90"
                >
                  Connect Gmail
                </Button>
              )}
            </div>
          )}

          {values.emailMethod === "smtp" && (
            <div className="space-y-3">
              <div className="grid gap-3 sm:grid-cols-2">
                <div className="space-y-1.5">
                  <Label className="font-headline text-sm text-ink">
                    SMTP host
                  </Label>
                  <Input
                    value={values.emailSmtpHost}
                    onChange={(e) => update({ emailSmtpHost: e.target.value })}
                    placeholder="smtp.gmail.com"
                  />
                </div>
                <div className="space-y-1.5">
                  <Label className="font-headline text-sm text-ink">Port</Label>
                  <Input
                    type="number"
                    value={values.emailSmtpPort}
                    onChange={(e) => update({ emailSmtpPort: e.target.value })}
                    placeholder="465"
                  />
                </div>
              </div>
              <div className="space-y-1.5">
                <Label className="font-headline text-sm text-ink">
                  Sender email
                </Label>
                <Input
                  type="email"
                  value={values.emailSender}
                  onChange={(e) => update({ emailSender: e.target.value })}
                  placeholder="you@gmail.com"
                />
              </div>
              <div className="space-y-1.5">
                <Label className="font-headline text-sm text-ink">
                  App password
                </Label>
                <Input
                  type="password"
                  value={values.emailPassword}
                  onChange={(e) => update({ emailPassword: e.target.value })}
                  placeholder="App-specific password"
                />
              </div>
              <Button
                variant="outline"
                size="sm"
                onClick={handleSmtpTest}
                disabled={smtpTesting}
              >
                {smtpTesting ? "Testing..." : "Test connection"}
              </Button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
