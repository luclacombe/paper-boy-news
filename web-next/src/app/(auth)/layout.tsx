import { NewspaperMasthead } from "@/components/newspaper-masthead";

export default function AuthLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="flex min-h-screen items-center justify-center bg-newsprint page-vignette px-6">
      <div className="w-full max-w-sm">
        {/* Masthead */}
        <div className="mb-8">
          <NewspaperMasthead
            subtitle="Sign in to continue."
            showDateline={false}
            compact
          />
        </div>
        {children}
      </div>
    </div>
  );
}
