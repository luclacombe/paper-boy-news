import Link from "next/link";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Privacy Policy — Paper Boy News",
};

export default function PrivacyPage() {
  return (
    <div className="mx-auto max-w-2xl px-6 py-16">
      <header className="mb-12 text-center">
        <Link
          href="/"
          className="font-display text-sm uppercase tracking-widest text-caption hover:text-ink"
        >
          Paper Boy News
        </Link>
        <h1 className="mt-4 font-display text-3xl font-bold text-ink sm:text-4xl">
          Privacy Policy
        </h1>
        <p className="mt-2 font-body text-sm italic text-caption">
          Last updated: November 9, 2026
        </p>
      </header>

      <div className="legal-prose space-y-8 font-body text-sm leading-relaxed text-ink/90">
        <section>
          <h2 className="mb-3 font-headline text-lg font-bold text-ink">
            What Paper Boy News Is
          </h2>
          <p>
            Paper Boy News (www.paper-boy-news.com) is a free, open-source tool
            that compiles the RSS news feeds you choose into an EPUB newspaper
            and delivers it to your e-reader each morning. The source code is
            publicly available on{" "}
            <a
              href="https://github.com/luclacombe/paper-boy-news"
              className="underline hover:no-underline"
              target="_blank"
              rel="noopener noreferrer"
            >
              GitHub
            </a>
            . This policy explains what data the service collects, how it is
            used, and how you can delete it.
          </p>
        </section>

        <div className="h-px bg-rule-gray/40" />

        <section>
          <h2 className="mb-3 font-headline text-lg font-bold text-ink">
            Data We Collect
          </h2>
          <p className="mb-3">
            We store the minimum needed to operate the service:
          </p>
          <ul className="list-disc space-y-1.5 pl-5">
            <li>
              <strong>Account info:</strong> your email address, and your name
              if you sign in with Google
            </li>
            <li>
              <strong>Newspaper preferences:</strong> your RSS feeds, newspaper
              title, device type, delivery method, delivery email address,
              delivery time, and timezone
            </li>
            <li>
              <strong>Delivery credentials:</strong> if you choose Google Drive
              delivery, an OAuth token limited to files the app creates (see
              below). Email delivery uses Resend; no credentials are stored
            </li>
            <li>
              <strong>OPDS sync token:</strong> if you enable wireless sync, a
              randomly generated access token for your personal OPDS feed
            </li>
            <li>
              <strong>Delivery history:</strong> a log of your past newspaper
              builds (date, status, article count, headlines)
            </li>
          </ul>
        </section>

        <div className="h-px bg-rule-gray/40" />

        <section>
          <h2 className="mb-3 font-headline text-lg font-bold text-ink">
            Google User Data
          </h2>
          <p>
            Paper Boy News uses Google APIs in two optional ways: signing in
            with your Google account, and delivering newspapers to your Google
            Drive.
          </p>

          <h3 className="mb-2 mt-4 font-headline text-base font-bold text-ink">
            What we access
          </h3>
          <ul className="list-disc space-y-1.5 pl-5">
            <li>
              <strong>Google sign-in</strong> (scopes: openid, email,
              profile): your Google account ID, email address, name, and
              profile picture URL. We do not access your contacts, calendar,
              Gmail, or any other Google data.
            </li>
            <li>
              <strong>Google Drive delivery</strong> (scope: drive.file, only
              if you choose it): permission to create a newspaper folder in
              your Drive, upload each edition as an EPUB file, and remove old
              editions that the app itself uploaded. This scope cannot see,
              read, or change any other file in your Drive.
            </li>
          </ul>

          <h3 className="mb-2 mt-4 font-headline text-base font-bold text-ink">
            How we use it
          </h3>
          <ul className="list-disc space-y-1.5 pl-5">
            <li>
              Your email address and Google account ID identify your account
              and let you sign in. Your email is also used to send you service
              notices, such as a failed delivery.
            </li>
            <li>
              The Drive token is used only to upload your newspaper to your
              chosen folder and remove that folder&apos;s older editions.
            </li>
            <li>
              Google user data is not used for advertising, profiling, or to
              train AI or machine-learning models.
            </li>
          </ul>

          <h3 className="mb-2 mt-4 font-headline text-base font-bold text-ink">
            How we store and protect it
          </h3>
          <p>
            Sign-in details and Drive tokens are stored in our Supabase
            database, which is encrypted at rest and accessed over encrypted
            (TLS) connections. Database rules restrict each account to its own
            data. Drive tokens are read only by the automated build process
            that delivers your newspaper.
          </p>

          <h3 className="mb-2 mt-4 font-headline text-base font-bold text-ink">
            Sharing
          </h3>
          <p>
            We do not sell, rent, or share Google user data with anyone. It is
            only processed by the infrastructure providers listed under
            Third-Party Services, solely to run the service, and is never
            transferred to third parties for any other purpose.
          </p>

          <h3 className="mb-2 mt-4 font-headline text-base font-bold text-ink">
            Retention and deletion
          </h3>
          <p>
            Google user data is kept only while your account exists. Deleting
            your account (Settings &gt; Account) immediately removes your
            profile, Drive tokens, and sign-in record. You can also revoke
            Paper Boy News&apos;s access at any time from your{" "}
            <a
              href="https://myaccount.google.com/permissions"
              className="underline hover:no-underline"
              target="_blank"
              rel="noopener noreferrer"
            >
              Google Account permissions page
            </a>
            . Files already delivered to your Drive stay there until you
            delete them.
          </p>

          <h3 className="mb-2 mt-4 font-headline text-base font-bold text-ink">
            Limited Use
          </h3>
          <p>
            Paper Boy News&apos;s use and transfer of information received from
            Google APIs adheres to the{" "}
            <a
              href="https://developers.google.com/terms/api-services-user-data-policy"
              className="underline hover:no-underline"
              target="_blank"
              rel="noopener noreferrer"
            >
              Google API Services User Data Policy
            </a>
            , including the Limited Use requirements.
          </p>
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
              We do not see or store your Google password. Sign-in goes through
              Google&apos;s own OAuth flow
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
            hosted PostgreSQL database. EPUB files are stored in Supabase
            Storage so you can download past editions from your dashboard, and
            are deleted with your account.
          </p>
        </section>

        <div className="h-px bg-rule-gray/40" />

        <section>
          <h2 className="mb-3 font-headline text-lg font-bold text-ink">
            Third-Party Services
          </h2>
          <ul className="list-disc space-y-1.5 pl-5">
            <li>
              <strong>Supabase:</strong> authentication, database, and file
              storage
            </li>
            <li>
              <strong>Vercel:</strong> web app hosting
            </li>
            <li>
              <strong>GitHub Actions:</strong> the automated newspaper build
              pipeline
            </li>
            <li>
              <strong>Resend:</strong> sending newspapers and service emails
            </li>
            <li>
              <strong>Google APIs:</strong> sign-in and (optionally) Drive
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
            You can delete your account and all associated data directly from
            Settings &gt; Account in the app. Deletion is immediate and
            permanent: your profile, feeds, delivery history, stored EPUBs,
            and any Google OAuth tokens are removed. You can also contact us
            at{" "}
            <a
              href="mailto:contact@paper-boy-news.com"
              className="underline hover:no-underline"
            >
              contact@paper-boy-news.com
            </a>{" "}
            if you need assistance.
          </p>
        </section>

        <div className="h-px bg-rule-gray/40" />

        <section>
          <h2 className="mb-3 font-headline text-lg font-bold text-ink">
            Contact
          </h2>
          <p>
            Paper Boy News is a personal project run by Luc Lacombe. Questions
            about this policy or your data:{" "}
            <a
              href="mailto:contact@paper-boy-news.com"
              className="underline hover:no-underline"
            >
              contact@paper-boy-news.com
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
            If this policy changes, the updated version will be posted here with
            a new date.
          </p>
        </section>
      </div>

      <footer className="mt-16 border-t border-rule-gray/40 pt-6 text-center font-body text-xs text-caption">
        <Link href="/" className="underline hover:no-underline">
          Back to Paper Boy News
        </Link>
        {" · "}
        <Link href="/terms" className="underline hover:no-underline">
          Terms of Service
        </Link>
      </footer>
    </div>
  );
}
