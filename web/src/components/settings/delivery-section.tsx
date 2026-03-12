"use client";

import { useState, useTransition } from "react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import {
  getGoogleAuthUrl,
  disconnectGoogle,
} from "@/actions/google-oauth";
import {
  enableOpdsSync,
  disableOpdsSync,
  regenerateOpdsUrl,
} from "@/actions/opds";
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
  opdsEnabled: boolean;
  opdsUrl: string;
}

interface DeliverySectionProps {
  values: DeliveryValues;
  onChange: (values: DeliveryValues) => void;
  hasDrive: boolean;
  hasGmail: boolean;
  onOpdsChange: (enabled: boolean, url: string | null) => void;
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
  onOpdsChange,
}: DeliverySectionProps) {
  const router = useRouter();
  const [isPending, startTransition] = useTransition();
  const [smtpTesting, setSmtpTesting] = useState(false);
  const [opdsBusy, setOpdsBusy] = useState(false);
  const [copyLabel, setCopyLabel] = useState("Copy");

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
      const res = await fetch("/api/smtp-test", {
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
          {hasDrive ? (
            <div className="flex items-center gap-3">
              <span className="font-body text-xs italic text-delivered">
                Google Drive connected
              </span>
              <Button
                variant="outline"
                size="sm"
                onClick={handleGoogleDisconnect}
                disabled={isPending}
                className="font-body text-xs"
              >
                Disconnect
              </Button>
            </div>
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
          {values.device === "kobo" && (
            <div className="border-l-2 border-rule-gray/50 pl-3">
              <p className="font-headline text-xs font-bold text-ink">
                Kobo setup
              </p>
              <p className="mt-1 font-body text-xs text-caption">
                Google Drive sync is supported on{" "}
                <strong>Kobo Forma, Sage, Elipsa, Elipsa 2E, and Libra Colour</strong>{" "}
                (firmware 4.37+). Clara models and older devices don&apos;t
                support it &mdash; choose Download instead.
              </p>
              <ol className="mt-1.5 list-decimal space-y-0.5 pl-4 font-body text-xs text-caption">
                <li>
                  On your Kobo, tap{" "}
                  <strong>More &rarr; My Google Drive &rarr; Get Started</strong>
                </li>
                <li>Note the code shown on screen</li>
                <li>
                  On a computer or phone, visit{" "}
                  <strong>kobo.com/googledrive</strong> and enter the code
                </li>
                <li>
                  Authorize Kobo to access the same Google account you connected
                  above
                </li>
                <li>
                  Paper Boy will place your newspaper in the{" "}
                  <strong>
                    {values.googleDriveFolder || "Rakuten Kobo"}
                  </strong>{" "}
                  folder &mdash; sync your Kobo over Wi-Fi to download it
                </li>
              </ol>
            </div>
          )}
        </div>
      )}

      {/* Email config */}
      {values.deliveryMethod === "email" && (
        <div className="space-y-3">
          {values.device === "kindle" && (
            <div className="space-y-3">
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
              <div className="border-l-2 border-rule-gray/50 pl-3">
                <p className="font-headline text-xs font-bold text-ink">
                  Kindle setup
                </p>
                <ol className="mt-1 list-decimal space-y-0.5 pl-4 font-body text-xs text-caption">
                  <li>
                    Find your Kindle email: on your Kindle, go to{" "}
                    <strong>Settings &rarr; Your Account</strong> &mdash;
                    it ends in <strong>@kindle.com</strong>
                  </li>
                  <li>
                    Approve the sender: go to{" "}
                    <strong>
                      amazon.com &rarr; Manage Your Content and Devices &rarr;
                      Preferences &rarr; Personal Document Settings
                    </strong>
                  </li>
                  <li>
                    Add the email address Paper Boy sends from to your{" "}
                    <strong>Approved Personal Document E-mail List</strong>
                  </li>
                </ol>
                <p className="mt-1.5 font-body text-xs text-caption">
                  Works with all Kindle devices and the Kindle app. EPUB files
                  are converted automatically.
                </p>
              </div>
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
              {hasGmail ? (
                <div className="flex items-center gap-3">
                  <span className="font-body text-xs italic text-delivered">
                    Gmail connected
                  </span>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={handleGoogleDisconnect}
                    disabled={isPending}
                    className="font-body text-xs"
                  >
                    Disconnect
                  </Button>
                </div>
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

      {/* KOReader wireless sync — independent of delivery method */}
      <div className="border-t border-rule-gray/50 pt-4">
        <label className="flex items-start gap-3">
          <input
            type="checkbox"
            checked={values.opdsEnabled}
            onChange={async (e) => {
              const enable = e.target.checked;
              setOpdsBusy(true);
              try {
                if (enable) {
                  const { url } = await enableOpdsSync();
                  onOpdsChange(true, url);
                  router.refresh();
                } else {
                  await disableOpdsSync();
                  onOpdsChange(false, null);
                  router.refresh();
                }
              } catch {
                toast.error(
                  enable
                    ? "Failed to enable wireless sync"
                    : "Failed to disable wireless sync"
                );
              } finally {
                setOpdsBusy(false);
              }
            }}
            disabled={opdsBusy}
            className="mt-1 h-4 w-4 accent-ink"
          />
          <div>
            <span className="font-headline text-sm font-bold text-ink">
              Enable wireless sync via KOReader
            </span>
            <p className="font-body text-xs text-caption">
              Automatically download your paper on any e-reader running
              KOReader &mdash; no USB cable needed.
            </p>
          </div>
        </label>

        {values.opdsEnabled && values.opdsUrl && (
          <div className="mt-3 space-y-3 pl-7">
            {/* Feed URL */}
            <div className="space-y-1.5">
              <Label className="font-headline text-sm text-ink">
                Personal feed URL
              </Label>
              <div className="flex gap-2">
                <Input
                  value={values.opdsUrl}
                  readOnly
                  className="font-mono text-xs"
                  onClick={(e) => (e.target as HTMLInputElement).select()}
                />
                <Button
                  variant="outline"
                  size="sm"
                  className="shrink-0 font-body text-xs"
                  onClick={async () => {
                    await navigator.clipboard.writeText(values.opdsUrl);
                    setCopyLabel("Copied!");
                    setTimeout(() => setCopyLabel("Copy"), 2000);
                  }}
                >
                  {copyLabel}
                </Button>
              </div>
            </div>

            {/* Regenerate URL */}
            <div className="flex items-center gap-3">
              <Button
                variant="outline"
                size="sm"
                className="font-body text-xs"
                disabled={opdsBusy}
                onClick={async () => {
                  setOpdsBusy(true);
                  try {
                    const { url } = await regenerateOpdsUrl();
                    onOpdsChange(true, url);
                    router.refresh();
                    toast.success("Feed URL regenerated");
                  } catch {
                    toast.error("Failed to regenerate URL");
                  } finally {
                    setOpdsBusy(false);
                  }
                }}
              >
                New URL
              </Button>
              <span className="font-body text-xs text-caption">
                This will disconnect any devices using the current URL.
              </span>
            </div>

            {/* Setup instructions */}
            <div className="border-l-2 border-rule-gray/50 pl-3">
              <p className="font-headline text-xs font-bold text-ink">
                How to connect your e-reader
              </p>
              <ol className="mt-1.5 list-decimal space-y-0.5 pl-4 font-body text-xs text-caption">
                <li>
                  Install KOReader on your device (Kobo: copy files to SD card,
                  reMarkable: use Toltec)
                </li>
                <li>In KOReader, open the file manager</li>
                <li>Tap the OPDS icon (looks like a signal/broadcast icon)</li>
                <li>Tap &ldquo;Add new OPDS catalog&rdquo;</li>
                <li>
                  Paste the URL above &mdash; leave username and password empty
                </li>
                <li>
                  Your paper will appear in the catalog each morning
                </li>
              </ol>
              <p className="mt-1.5 font-body text-xs text-caption">
                Works with Kobo (all models), reMarkable, PocketBook, and Kindle
                (requires jailbreak).
              </p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
