import type { UserConfig, SetupStatus } from "@/types";

export function computeSetupStatus(
  config: UserConfig,
  editionCount: number,
  hasDrive: boolean,
  hasGmail: boolean
): SetupStatus {
  const isFirstVisit = editionCount === 0;

  const needsDriveAuth =
    config.deliveryMethod === "google_drive" && !hasDrive;

  const needsGmailAuth =
    config.deliveryMethod === "email" &&
    config.emailMethod === "gmail" &&
    !hasGmail;

  const needsSmtpConfig =
    config.deliveryMethod === "email" &&
    config.emailMethod === "smtp" &&
    (!config.emailSmtpHost || !config.emailSender || !config.emailPassword);

  const needsKindleEmail =
    config.device === "kindle" &&
    config.deliveryMethod === "email" &&
    !config.kindleEmail;

  const isFullyConfigured =
    !needsDriveAuth &&
    !needsGmailAuth &&
    !needsSmtpConfig &&
    !needsKindleEmail;

  return {
    isFirstVisit,
    needsDriveAuth,
    needsGmailAuth,
    needsSmtpConfig,
    needsKindleEmail,
    isFullyConfigured,
  };
}
