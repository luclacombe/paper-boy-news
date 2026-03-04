import Link from "next/link";

export default function AuthLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="flex min-h-screen items-center justify-center bg-newsprint px-6">
      <div className="w-full max-w-sm">
        {/* Masthead */}
        <div className="mb-8 text-center">
          <Link
            href="/"
            className="font-display text-3xl font-black uppercase tracking-[0.15em] text-ink"
          >
            Paper Boy
          </Link>
          <div className="mx-auto mt-3 h-px w-24 bg-rule-gray" />
        </div>
        {children}
      </div>
    </div>
  );
}
