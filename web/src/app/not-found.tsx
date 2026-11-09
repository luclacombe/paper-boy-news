import Link from "next/link";
import { NewspaperMasthead } from "@/components/newspaper-masthead";

export default function NotFound() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-newsprint page-vignette px-6">
      <main className="w-full max-w-sm text-center">
        <NewspaperMasthead showDateline={false} compact />
        <h2 className="mt-8 font-display text-xl font-bold uppercase tracking-wider text-ink">
          Page Not Found
        </h2>
        <p className="mt-3 font-body text-sm text-caption">
          This page didn&rsquo;t make it into today&rsquo;s edition.
        </p>
        <Link
          href="/"
          className="mt-6 inline-block font-mono text-xs uppercase tracking-widest text-ink underline underline-offset-4 hover:text-edition-red"
        >
          Back to the front page
        </Link>
      </main>
    </div>
  );
}
