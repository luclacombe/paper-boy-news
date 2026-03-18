import type { UserConfig, SetupStatus } from "@/types";

export function computeSetupStatus(
  config: UserConfig,
  editionCount: number,
  hasDrive: boolean
): SetupStatus {
  const isFirstVisit = editionCount === 0;

  const needsDriveAuth =
    config.deliveryMethod === "google_drive" && !hasDrive;

  const needsRecipientEmail =
    config.deliveryMethod === "email" && !config.recipientEmail;

  const isFullyConfigured = !needsDriveAuth && !needsRecipientEmail;

  return {
    isFirstVisit,
    needsDriveAuth,
    needsRecipientEmail,
    isFullyConfigured,
  };
}
