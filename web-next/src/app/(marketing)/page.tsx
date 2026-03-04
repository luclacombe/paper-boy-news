import Link from "next/link";

export default function LandingPage() {
  return (
    <main className="mx-auto max-w-2xl px-6 py-16">
      {/* Masthead */}
      <div className="text-center">
        <div className="mx-auto mb-4 h-[3px] w-full bg-ink" />
        <h1 className="font-display text-5xl font-black uppercase tracking-[0.15em] text-ink sm:text-6xl">
          Paper Boy
        </h1>
        <p className="mt-2 font-body text-lg font-light text-caption">
          Your morning newspaper, built overnight for your e-reader.
        </p>
        <div className="mx-auto mt-4 h-px w-full bg-rule-gray" />
      </div>

      {/* How it works */}
      <section className="mt-16">
        <h2 className="mb-8 text-center font-display text-xl font-bold uppercase tracking-wider text-ink">
          How It Works
        </h2>
        <div className="grid grid-cols-1 gap-8 sm:grid-cols-3">
          {[
            {
              step: "1",
              title: "Choose Sources",
              description:
                "Pick from curated RSS feeds or add your own. Tech, world news, business — your mix.",
            },
            {
              step: "2",
              title: "We Build It Overnight",
              description:
                "Every morning, we fetch your feeds, extract full articles, and compile a beautiful EPUB.",
            },
            {
              step: "3",
              title: "Read on Your E-Reader",
              description:
                "Delivered to your Kindle, Kobo, or reMarkable. Ready when you wake up.",
            },
          ].map((item) => (
            <div key={item.step} className="text-center">
              <div className="mx-auto mb-3 flex h-10 w-10 items-center justify-center rounded-full border-2 border-ink font-mono text-sm font-bold text-ink">
                {item.step}
              </div>
              <h3 className="font-headline text-base font-bold text-ink">
                {item.title}
              </h3>
              <p className="mt-2 font-body text-sm text-caption">
                {item.description}
              </p>
            </div>
          ))}
        </div>
      </section>

      {/* CTA */}
      <section className="mt-16 text-center">
        <div className="mx-auto mb-6 h-px w-32 bg-rule-gray" />
        <p className="mb-6 font-headline text-base italic text-caption">
          Free. Open source. No ads. No tracking.
        </p>
        <Link
          href="/signup"
          className="inline-flex items-center rounded-sm bg-ink px-8 py-3 font-body text-sm font-semibold uppercase tracking-wider text-newsprint transition-colors hover:bg-ink/90"
        >
          Get Started
        </Link>
        <p className="mt-3 font-body text-xs text-caption">
          Set up in under 2 minutes
        </p>
      </section>
    </main>
  );
}
