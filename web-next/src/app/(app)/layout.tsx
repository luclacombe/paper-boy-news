import { redirect } from "next/navigation";
import { getUserProfile } from "@/lib/auth";
import { AppHeader } from "@/components/app-header";

export default async function AppLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  let profile;
  try {
    profile = await getUserProfile();
  } catch {
    redirect("/login");
  }

  if (!profile || !profile.onboardingComplete) {
    redirect("/onboarding");
  }

  return (
    <div className="min-h-screen bg-newsprint page-vignette">
      <AppHeader />
      <main className="mx-auto max-w-2xl px-6 py-8">{children}</main>
    </div>
  );
}
