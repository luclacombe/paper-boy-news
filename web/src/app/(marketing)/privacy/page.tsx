import Link from "next/link";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Privacy Policy — Paper Boy",
};

export default function PrivacyPage() {
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
          Privacy Policy
        </h1>
        <p className="mt-2 font-body text-sm italic text-caption">
          Last updated: March 8, 2026
        </p>
      </header>

      <div className="legal-prose space-y-8 font-body text-sm leading-relaxed text-ink/90">
        <section>
          <h2 className="mb-3 font-headline text-lg font-bold text-ink">
            What Paper Boy Is
          </h2>
          <p>
            Paper Boy is a free, open-source tool that compiles RSS feeds into
            EPUB newspapers and delivers them to your e-reader. The source code
            is publicly available on GitHub.
          </p>
        </section>

        <div className="h-px bg-rule-gray/40" />

        <section>
          <h2 className="mb-3 font-headline text-lg font-bold text-ink">
            Data We Collect
          </h2>
          <p className="mb-3">
            When you create an account, we store the minimum needed to operate
            the service:
          </p>
          <ul className="list-disc space-y-1.5 pl-5">
            <li>
              <strong>Account info</strong> — email address and name (from
              Google sign-in or email registration)
            </li>
            <li>
              <strong>Newspaper preferences</strong> — your RSS feeds, device
              type, delivery method, delivery time, and timezone
            </li>
            <li>
              <strong>Delivery credentials</strong> — if you choose email
              delivery, your SMTP settings; if you choose Google Drive, an OAuth
              token scoped to Google Drive file creation only
            </li>
            <li>
              <strong>Delivery history</strong> — a log of your past newspaper
              builds (date, status, article count)
            </li>
          </ul>
        </section>

        <div className="h-px bg-rule-gray/40" />

        <section>
          <h2 className="mb-3 font-headline text-lg font-bold text-ink">
            What We Don&apos;t Do
          </h2>
          <ul className="list-disc space-y-1.5 pl-5">
            <li>We do not sell, share, or monetize your data</li>
            <li>We do not run ads or tracking scripts</li>
            <li>We do not use analytics services</li>
            <li>We do not read the content of your newspapers after delivery</li>
            <li>
              We do not store your Google password — authentication goes through
              Google&apos;s OAuth flow and we only receive a scoped token
            </li>
          </ul>
        </section>

        <div className="h-px bg-rule-gray/40" />

        <section>
          <h2 className="mb-3 font-headline text-lg font-bold text-ink">
            Where Data Is Stored
          </h2>
          <p>
            Your data is stored in a{" "}
            <a
              href="https://supabase.com"
              className="underline hover:no-underline"
              target="_blank"
              rel="noopener noreferrer"
            >
              Supabase
            </a>{" "}
            hosted PostgreSQL database. EPUB files are temporarily stored in
            Supabase Storage and are available for download for a limited time
            after each build.
          </p>
        </section>

        <div className="h-px bg-rule-gray/40" />

        <section>
          <h2 className="mb-3 font-headline text-lg font-bold text-ink">
            Third-Party Services
          </h2>
          <ul className="list-disc space-y-1.5 pl-5">
            <li>
              <strong>Supabase</strong> — authentication and database hosting
            </li>
            <li>
              <strong>Vercel</strong> — web app hosting
            </li>
            <li>
              <strong>GitHub Actions</strong> — newspaper build pipeline
            </li>
            <li>
              <strong>Google APIs</strong> — sign-in and (optionally) Drive
              delivery
            </li>
          </ul>
          <p className="mt-3">
            Each service has its own privacy policy. We only send these services
            the minimum data required to operate.
          </p>
        </section>

        <div className="h-px bg-rule-gray/40" />

        <section>
          <h2 className="mb-3 font-headline text-lg font-bold text-ink">
            Deleting Your Data
          </h2>
          <p>
            You can request deletion of your account and all associated data by
            emailing{" "}
            <a
              href="mailto:luc.c.lacombe@gmail.com"
              className="underline hover:no-underline"
            >
              luc.c.lacombe@gmail.com
            </a>
            . We will delete your data within 30 days.
          </p>
        </section>

        <div className="h-px bg-rule-gray/40" />

        <section>
          <h2 className="mb-3 font-headline text-lg font-bold text-ink">
            Changes
          </h2>
          <p>
            If this policy changes, the updated version will be posted here with
            a new date. Paper Boy is a personal project — the policy is kept
            simple because the project is simple.
          </p>
        </section>
      </div>

      <footer className="mt-16 border-t border-rule-gray/40 pt-6 text-center font-body text-xs text-caption">
        <Link href="/" className="underline hover:no-underline">
          Back to Paper Boy
        </Link>
        {" · "}
        <Link href="/terms" className="underline hover:no-underline">
          Terms of Service
        </Link>
      </footer>
    </div>
  );
}
