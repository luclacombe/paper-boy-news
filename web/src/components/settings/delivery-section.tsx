"use client";

import { useState, useEffect, useTransition } from "react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import {
  getGoogleAuthUrl,
  disconnectGoogle,
} from "@/actions/google-oauth";
import {
  enableOpdsSync,
  regenerateOpdsUrl,
} from "@/actions/opds";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import { cn } from "@/lib/utils";
import { DEVICES, defaultDriveFolderForDevice } from "@/lib/constants";
import type { Device, DeliveryMethod } from "@/types";

export interface DeliveryValues {
  device: Device;
  deliveryMethod: DeliveryMethod;
  recipientEmail: string;
  googleDriveFolder: string;
}

interface DeliverySectionProps {
  values: DeliveryValues;
  onChange: (values: DeliveryValues) => void;
  hasDrive: boolean;
  opdsUrl: string;
  onOpdsUrlChange: (url: string) => void;
  userEmail?: string;
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
          description: "Auto-sync via Kobo's built-in Google Drive",
        },
        {
          value: "local",
          label: "Download",
          description: "Download EPUB and transfer manually",
        },
        {
          value: "koreader",
          label: "Wireless sync",
          description:
            "Auto-download over WiFi via KOReader. Requires one-time setup on your device",
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
        {
          value: "koreader",
          label: "Wireless sync",
          description:
            "Auto-download via KOReader. Requires jailbreak and setup",
        },
      ];
    case "remarkable":
      return [
        {
          value: "email",
          label: "Email",
          description: "Send EPUB to an email address",
        },
        {
          value: "google_drive",
          label: "Google Drive",
          description: "Sync via Google Drive. Access from your reMarkable's app",
        },
        {
          value: "local",
          label: "Download",
          description: "Download EPUB and transfer via USB or app",
        },
        {
          value: "koreader",
          label: "Wireless sync",
          description:
            "Auto-download over WiFi via KOReader. Requires one-time setup on your device",
        },
      ];
    default:
      return [
        {
          value: "email",
          label: "Email",
          description: "Send EPUB to an email address",
        },
        {
          value: "google_drive",
          label: "Google Drive",
          description: "Sync via Google Drive. Access your paper from any device",
        },
        {
          value: "local",
          label: "Download",
          description: "Download EPUB and transfer to your device",
        },
        {
          value: "koreader",
          label: "Wireless sync",
          description:
            "Auto-download over WiFi via KOReader. Requires third-party app setup",
        },
      ];
  }
}

function KoboSetupInstructions() {
  return (
    <>
      <p className="font-headline text-xs font-bold text-ink">
        How to set up on Kobo
      </p>
      <ol className="mt-1.5 list-decimal space-y-1 pl-4 font-body text-xs text-caption">
        <li>
          Download KOReader from the{" "}
          <a
            href="https://github.com/koreader/koreader/wiki/Installation-on-Kobo-devices"
            target="_blank"
            rel="noopener noreferrer"
            className="font-bold text-ink underline underline-offset-2"
          >
            KOReader wiki
          </a>
        </li>
        <li>
          Connect your Kobo to a computer via USB, then unzip the KOReader download
          into the root of your Kobo&apos;s storage
        </li>
        <li>
          Eject your Kobo. KOReader will appear as a second reading app
        </li>
        <li>
          Open KOReader, go to the file manager, and tap the OPDS icon
          (looks like a broadcast/signal icon at the top)
        </li>
        <li>Tap &ldquo;Add new OPDS catalog&rdquo; and paste the URL above</li>
        <li>
          Your paper will appear in the catalog each morning. Just tap to
          download
        </li>
      </ol>
      <p className="mt-1.5 font-body text-xs text-caption">
        Works with all Kobo models. No jailbreak needed.
      </p>
    </>
  );
}

function RemarkableSetupInstructions() {
  return (
    <>
      <p className="font-headline text-xs font-bold text-ink">
        How to set up on reMarkable
      </p>
      <ol className="mt-1.5 list-decimal space-y-1 pl-4 font-body text-xs text-caption">
        <li>
          Install the{" "}
          <a
            href="https://toltec-dev.org/"
            target="_blank"
            rel="noopener noreferrer"
            className="font-bold text-ink underline underline-offset-2"
          >
            Toltec
          </a>{" "}
          package manager on your reMarkable
        </li>
        <li>
          Install KOReader via Toltec. See the{" "}
          <a
            href="https://github.com/koreader/koreader/wiki/Installation-on-reMarkable"
            target="_blank"
            rel="noopener noreferrer"
            className="font-bold text-ink underline underline-offset-2"
          >
            full guide
          </a>
        </li>
        <li>
          Open KOReader, go to the file manager, and tap the OPDS icon
        </li>
        <li>Tap &ldquo;Add new OPDS catalog&rdquo; and paste the URL above</li>
        <li>Your paper will appear in the catalog each morning</li>
      </ol>
    </>
  );
}

function KindleSetupInstructions() {
  return (
    <>
      <p className="font-headline text-xs font-bold text-ink">
        How to set up on Kindle
      </p>
      <p className="mt-1 font-body text-xs text-caption">
        Your Kindle must be jailbroken to use KOReader. If it isn&apos;t,
        use <strong>Send-to-Kindle</strong> instead.
      </p>
      <ol className="mt-1.5 list-decimal space-y-1 pl-4 font-body text-xs text-caption">
        <li>
          Install KOReader via KUAL. See the{" "}
          <a
            href="https://github.com/koreader/koreader/wiki/Installation-on-Kindle-devices"
            target="_blank"
            rel="noopener noreferrer"
            className="font-bold text-ink underline underline-offset-2"
          >
            full guide
          </a>
        </li>
        <li>
          Open KOReader, go to the file manager, and tap the OPDS icon
        </li>
        <li>Tap &ldquo;Add new OPDS catalog&rdquo; and paste the URL above</li>
        <li>Your paper will appear in the catalog each morning</li>
      </ol>
    </>
  );
}

function OtherSetupInstructions() {
  return (
    <>
      <p className="font-headline text-xs font-bold text-ink">
        How to set up wireless sync
      </p>
      <ol className="mt-1.5 list-decimal space-y-1 pl-4 font-body text-xs text-caption">
        <li>
          Install{" "}
          <a
            href="https://github.com/koreader/koreader/wiki"
            target="_blank"
            rel="noopener noreferrer"
            className="font-bold text-ink underline underline-offset-2"
          >
            KOReader
          </a>{" "}
          on your device
        </li>
        <li>
          Open KOReader, go to the file manager, and tap the OPDS icon
        </li>
        <li>Tap &ldquo;Add new OPDS catalog&rdquo; and paste the URL above</li>
        <li>Your paper will appear in the catalog each morning</li>
      </ol>
      <p className="mt-1.5 font-body text-xs text-caption">
        Works with Kobo, reMarkable, PocketBook, and jailbroken Kindle.
      </p>
    </>
  );
}

function getSetupInstructions(device: Device) {
  switch (device) {
    case "kobo":
      return <KoboSetupInstructions />;
    case "remarkable":
      return <RemarkableSetupInstructions />;
    case "kindle":
      return <KindleSetupInstructions />;
    default:
      return <OtherSetupInstructions />;
  }
}

export function DeliverySection({
  values,
  onChange,
  hasDrive,
  opdsUrl,
  onOpdsUrlChange,
  userEmail,
}: DeliverySectionProps) {
  const router = useRouter();
  const [isPending, startTransition] = useTransition();
  const [opdsBusy, setOpdsBusy] = useState(false);
  const [copyLabel, setCopyLabel] = useState("Copy");

  const methods = getDeliveryMethodsForDevice(values.device);

  function update(patch: Partial<DeliveryValues>) {
    onChange({ ...values, ...patch });
  }

  function handleDeviceChange(d: Device) {
    const newMethods = getDeliveryMethodsForDevice(d);
    update({
      device: d,
      deliveryMethod: newMethods[0].value,
      googleDriveFolder: defaultDriveFolderForDevice(d),
    });
  }

  // Auto-generate OPDS token when KOReader is selected and no URL exists
  useEffect(() => {
    if (values.deliveryMethod !== "koreader" || opdsUrl || opdsBusy) return;
    let cancelled = false;
    setOpdsBusy(true);
    enableOpdsSync()
      .then(({ url }) => {
        if (!cancelled) {
          onOpdsUrlChange(url);
          router.refresh();
        }
      })
      .catch(() => {
        if (!cancelled) toast.error("Failed to set up wireless sync");
      })
      .finally(() => {
        if (!cancelled) setOpdsBusy(false);
      });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [values.deliveryMethod]);

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

      {/* KOReader / Wireless sync config */}
      {values.deliveryMethod === "koreader" && (
        <div className="space-y-3">
          {/* Feed URL */}
          {opdsUrl ? (
            <>
              <div className="space-y-1.5">
                <Label className="font-headline text-sm text-ink">
                  Personal feed URL
                </Label>
                <div className="flex gap-2">
                  <Input
                    value={opdsUrl}
                    readOnly
                    className="font-mono text-xs"
                    onClick={(e) => (e.target as HTMLInputElement).select()}
                  />
                  <Button
                    variant="outline"
                    size="sm"
                    className="shrink-0 font-body text-xs"
                    onClick={async () => {
                      await navigator.clipboard.writeText(opdsUrl);
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
                      onOpdsUrlChange(url);
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
            </>
          ) : (
            <p className="font-body text-xs text-caption">
              {opdsBusy ? "Setting up wireless sync..." : "Generating your feed URL..."}
            </p>
          )}

          {/* Device-specific setup instructions */}
          {opdsUrl && (
            <div className="border-l-2 border-rule-gray/50 pl-3">
              {getSetupInstructions(values.device)}
            </div>
          )}
        </div>
      )}

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
              placeholder="Paper Boy News"
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
                support it. Choose Download instead.
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
                  Paper Boy News will place your newspaper in the{" "}
                  <strong>
                    {values.googleDriveFolder || "Rakuten Kobo"}
                  </strong>{" "}
                  folder. Sync your Kobo over Wi-Fi to download it
                </li>
              </ol>
            </div>
          )}
        </div>
      )}

      {/* Email config */}
      {values.deliveryMethod === "email" && (
        <div className="space-y-3">
          <div className="space-y-1.5">
            <Label className="font-headline text-sm text-ink">
              {values.device === "kindle"
                ? "Kindle email address"
                : "Email address"}
            </Label>
            <Input
              type="email"
              value={values.recipientEmail}
              onChange={(e) => update({ recipientEmail: e.target.value })}
              placeholder={
                values.device === "kindle"
                  ? "your-kindle@kindle.com"
                  : "you@example.com"
              }
            />
            <p className="font-body text-xs text-caption">
              Your newspaper will be sent from{" "}
              <strong>delivery@paper-boy-news.com</strong>
            </p>
            {userEmail &&
              values.recipientEmail &&
              values.recipientEmail !== userEmail && (
                <p className="font-body text-xs italic text-caption">
                  This is different from your account email ({userEmail}).
                </p>
              )}
          </div>

          {values.device === "kindle" && (
            <div className="border-l-2 border-rule-gray/50 pl-3">
              <p className="font-headline text-xs font-bold text-ink">
                Kindle setup
              </p>
              <ol className="mt-1 list-decimal space-y-0.5 pl-4 font-body text-xs text-caption">
                <li>
                  Find your Kindle email: on your Kindle, go to{" "}
                  <strong>Settings &rarr; Your Account</strong>.
                  It ends in <strong>@kindle.com</strong>
                </li>
                <li>
                  Approve the sender: go to{" "}
                  <strong>
                    amazon.com &rarr; Manage Your Content and Devices &rarr;
                    Preferences &rarr; Personal Document Settings
                  </strong>
                </li>
                <li>
                  Add <strong>delivery@paper-boy-news.com</strong> to your{" "}
                  <strong>Approved Personal Document E-mail List</strong>
                </li>
              </ol>
              <p className="mt-1.5 font-body text-xs text-caption">
                Works with all Kindle devices and the Kindle app. EPUB files
                are converted automatically.
              </p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
