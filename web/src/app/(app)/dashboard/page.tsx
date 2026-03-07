import { getUserConfig } from "@/actions/user-config";
import { getFeeds } from "@/actions/feeds";
import { getDeliveryHistory, getEditionCount } from "@/actions/delivery-history";
import { hasDriveScope, hasGmailScope } from "@/actions/google-oauth";
import { computeSetupStatus } from "@/lib/setup-status";
import {
  getEditionDate,
  isBeforeEditionCutoff,
  isBeforeDeliveryTime,
} from "@/lib/edition-date";
import { DashboardClient } from "@/components/dashboard-client";
import { AppMasthead } from "@/components/app-masthead";
import { redirect } from "next/navigation";

export default async function DashboardPage() {
  const [config, feeds, history, editionCount, hasDrive, hasGmail] =
    await Promise.all([
      getUserConfig(),
      getFeeds(),
      getDeliveryHistory(6),
      getEditionCount(),
      hasDriveScope(),
      hasGmailScope(),
    ]);

  if (!config) redirect("/login");

  const setupStatus = computeSetupStatus(config, editionCount, hasDrive, hasGmail);

  const editionDate = getEditionDate(config.timezone);
  const beforeCutoff = isBeforeEditionCutoff(config.timezone);
  const beforeDelivery = isBeforeDeliveryTime(
    config.deliveryTime,
    config.timezone
  );
  const todaysEdition =
    history.find((r) => r.editionDate === editionDate) ?? null;

  return (
    <>
      <AppMasthead newspaperTitle={config.title} />
      <main className="mx-auto max-w-3xl px-6 py-8">
        <DashboardClient
          config={config}
          feeds={feeds}
          history={history}
          setupStatus={setupStatus}
          editionDate={editionDate}
          isBeforeCutoff={beforeCutoff}
          isBeforeDelivery={beforeDelivery}
          todaysEdition={todaysEdition}
        />
      </main>
    </>
  );
}
