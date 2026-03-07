import { redirect } from "next/navigation";
import { getUserProfile } from "@/lib/auth";

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
      {children}
    </div>
  );
}
