import Link from "next/link";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Terms of Service — Paper Boy",
};

export default function TermsPage() {
  return (
    <div className="mx-auto max-w-2xl px-6 py-16">
      <header className="mb-12 text-center">
        <Link
          href="/"
          className="font-display text-sm uppercase tracking-widest text-caption hover:text-ink"
        >
          Paper Boy
        </Link>
        <h1 className="mt-4 font-display text-3xl font-bold text-ink sm:text-4xl">
          Terms of Service
        </h1>
        <p className="mt-2 font-body text-sm italic text-caption">
          Last updated: March 8, 2026
        </p>
      </header>

      <div className="legal-prose space-y-8 font-body text-sm leading-relaxed text-ink/90">
        <section>
          <h2 className="mb-3 font-headline text-lg font-bold text-ink">
            The Short Version
          </h2>
          <p>
            Paper Boy is a free, open-source personal project. You can use it to
            compile RSS feeds into newspapers for your e-reader. There are no
            fees, no subscriptions, and no catch.
          </p>
        </section>

        <div className="h-px bg-rule-gray/40" />

        <section>
          <h2 className="mb-3 font-headline text-lg font-bold text-ink">
            What You Get
          </h2>
          <ul className="list-disc space-y-1.5 pl-5">
            <li>
              An account to configure your newspaper (sources, device, delivery
              method, schedule)
            </li>
            <li>
              Automated daily EPUB builds delivered to your e-reader or available
              for download
            </li>
            <li>On-demand builds via the dashboard</li>
          </ul>
        </section>

        <div className="h-px bg-rule-gray/40" />

        <section>
          <h2 className="mb-3 font-headline text-lg font-bold text-ink">
            What We Expect
          </h2>
          <ul className="list-disc space-y-1.5 pl-5">
            <li>Use the service for personal, non-commercial purposes</li>
            <li>
              Don&apos;t abuse the build system (automated spam, excessive
              on-demand builds, etc.)
            </li>
            <li>
              Don&apos;t attempt to access other users&apos; data or interfere
              with the service
            </li>
          </ul>
        </section>

        <div className="h-px bg-rule-gray/40" />

        <section>
          <h2 className="mb-3 font-headline text-lg font-bold text-ink">
            Content
          </h2>
          <p>
            Paper Boy fetches and compiles content from RSS feeds you choose. We
            don&apos;t control, curate, or endorse any of that content. The
            articles belong to their original publishers.
          </p>
        </section>

        <div className="h-px bg-rule-gray/40" />

        <section>
          <h2 className="mb-3 font-headline text-lg font-bold text-ink">
            No Warranty
          </h2>
          <p>
            Paper Boy is provided &ldquo;as is&rdquo; without warranty of any
            kind. It&apos;s a personal project maintained in spare time.
            Deliveries may occasionally fail, feeds may change, and the service
            may have downtime. We&apos;ll do our best but make no guarantees.
          </p>
        </section>

        <div className="h-px bg-rule-gray/40" />

        <section>
          <h2 className="mb-3 font-headline text-lg font-bold text-ink">
            Account Termination
          </h2>
          <p>
            You can stop using Paper Boy at any time. We reserve the right to
            suspend accounts that abuse the service. If you want your data
            deleted, email{" "}
            <a
              href="mailto:luc.c.lacombe@gmail.com"
              className="underline hover:no-underline"
            >
              luc.c.lacombe@gmail.com
            </a>
            .
          </p>
        </section>

        <div className="h-px bg-rule-gray/40" />

        <section>
          <h2 className="mb-3 font-headline text-lg font-bold text-ink">
            Changes
          </h2>
          <p>
            These terms may be updated occasionally. Continued use of the
            service after changes constitutes acceptance. Material changes will
            be communicated through the app.
          </p>
        </section>
      </div>

      <footer className="mt-16 border-t border-rule-gray/40 pt-6 text-center font-body text-xs text-caption">
        <Link href="/" className="underline hover:no-underline">
          Back to Paper Boy
        </Link>
        {" · "}
        <Link href="/privacy" className="underline hover:no-underline">
          Privacy Policy
        </Link>
      </footer>
    </div>
  );
}
