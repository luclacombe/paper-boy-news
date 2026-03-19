import Link from "next/link";
import { NewspaperMasthead } from "@/components/newspaper-masthead";
import { MarginDecoration } from "@/components/margin-decoration";
import {
  ArchivalColumn,
  ArchivalStrip,
  type ArchivalStory,
} from "@/components/archival-column";

/* Archival image stories */

const LEFT_STORIES: ArchivalStory[] = [
  {
    src: "/archival/1.webp",
    headline: "EMPLOYEE OF THE MONTH:\nS. RUSSELL, KINDLE DIVISION",
    date: "May 2019",
    caption:
      "Russell, 12, of the Wilmington bureau, has maintained a flawless Send-to-Kindle record for two consecutive years. He personally handles all Kindle deliveries each morning before school.",
    url: "https://www.loc.gov/pictures/resource/nclc.03574/",
  },
  {
    src: "/archival/2.webp",
    headline: "FEED INTAKE CREW SCRAMBLES FOR THE MORNING URLS",
    date: "October 2021",
    caption:
      "The RSS intake team processes the morning's feed subscriptions by hand. Each URL is inspected, validated, and sorted before the presses can begin. The crew has filed a formal grievance about the growing number of international feeds but management has yet to respond.",
    url: "https://www.loc.gov/resource/ppmsca.44569/",
  },
  {
    src: "/archival/3.webp",
    headline: "QA TEAM ON STANDBY, PHILADELPHIA BUREAU",
    date: "June 2017",
    caption:
      "With the Sunday edition dispatched ahead of schedule, the Philadelphia quality assurance division finds itself briefly idle. Investigator Brown notes that morale remains high despite recent demands to also cover the reMarkable routes.",
    url: "https://www.loc.gov/item/2018675943/",
  },
  {
    src: "/archival/4.webp",
    headline: "ALPERT CLOCKS IN FOR EVENING FEED MAINTENANCE",
    date: "January 2023",
    caption:
      "Alpert, 12, of the New Haven office, reports to the Boys Club each evening to monitor overnight feed integrity. He has handled the trafilatura extraction pipeline for three years without a single malformed article reaching production.",
    url: "https://www.loc.gov/item/2018674595/",
  },
  {
    src: "/archival/5.webp",
    headline: "YOUNGEST RECRUIT HANDLES THE KOBO ROUTE",
    date: "November 2020",
    caption:
      "Sam, 5, is the youngest employee on the Paper Boy payroll. He reports for Google Drive sync duties at 5 A.M. sharp and covers the European and Asia-Pacific Kobo routes solo. The Beaumont office is apparently overrun with qualified candidates but none have matched his record. Zero missed sync windows this quarter.",
    url: "https://www.loc.gov/item/2018675238/",
  },
  {
    src: "/archival/6.webp",
    headline: "THE 6 A.M. BUILD: MORNING CREW REPORTS",
    date: "March 2018",
    caption:
      "The crew departs Burley's Branch at dawn to begin the daily feed cycle. Every subscriber's EPUB must be compiled and delivered before the first cup of coffee is poured. The St. Louis office has requested additional hands but headquarters has declined.",
    url: "https://www.loc.gov/item/2018675668/",
  },
  {
    src: "/archival/7.webp",
    headline: "GIBSON, 13: SEVEN YEARS ON THE DELIVERY BEAT",
    date: "August 2022",
    caption:
      "Gibson of the Wilmington bureau has been running subscriber deliveries since he was six. His brother handles internal dispatch between the compilation floor and the distribution dock. Gibson's request for a raise has been noted and filed. Management thanks him for his continued service.",
    url: "https://www.loc.gov/item/2018675883/",
  },
  {
    src: "/archival/8.webp",
    headline: "EPUB PRESS NO. 4 CLEARED FOR OVERNIGHT RUN",
    date: "February 2024",
    caption:
      "The overnight compilation press has been retooled and cleared for the full subscriber run. Each edition is assembled to order. No two EPUBs are alike. The press operators have expressed concern about the growing subscriber rolls but have been assured the equipment will hold.",
    url: "https://www.loc.gov/item/2016824489/",
  },
  {
    src: "/archival/9.webp",
    headline: "BUREAU OF COVER GENERATION, NIGHT OPERATIONS",
    date: "July 2016",
    caption:
      "The cover image division runs at full capacity through the night. Every subscriber receives a unique cover, hand-pulled from this press. The bureau has petitioned for a second shift but the cron job does not allow for delays.",
    url: "https://www.loc.gov/item/2019671194/",
  },
];

const RIGHT_STORIES: ArchivalStory[] = [
  {
    src: "/archival/10.webp",
    headline: "THE ORIGINAL PRESS: STILL IN DAILY SERVICE",
    date: "April 2017",
    caption:
      "The company's oldest press remains operational for legacy EPUB formats. Engineering has proposed decommissioning it several times, but it continues to produce editions for a small but loyal subscriber base who refuse to update their devices. It has never missed a morning.",
    url: "https://www.loc.gov/resource/cph.3a08789/",
  },
  {
    src: "/archival/11.webp",
    headline: "OVERNIGHT EPUB COMPILATION IN PROGRESS",
    date: "December 2022",
    caption:
      "The night shift runs the presses through the small hours. The workers have raised concerns about the ever-expanding subscriber list but by dawn the editions are bound and ready regardless.",
    url: "https://www.loc.gov/item/2019676582/",
  },
  {
    src: "/archival/12.webp",
    headline: "FINAL INSPECTION BEFORE MORNING DISPATCH",
    date: "September 2020",
    caption:
      "Each EPUB passes through manual inspection at the Stanford press. The inspector checks article extraction, image placement, and metadata before clearing the edition for delivery. He has not approved a break in several weeks but reports that quality remains acceptable.",
    url: "https://www.loc.gov/item/2019676605/",
  },
  {
    src: "/archival/13.webp",
    headline: "FOREMAN GOUDY INSPECTS THE FEED PIPELINE",
    date: "March 2024",
    caption:
      "Goudy reviews the morning's feedparser output at the main press. Each EPUB is inspected by hand before dispatch. He has formally requested that subscribers limit their RSS feeds to a reasonable number but has received no response from the board.",
    url: "https://www.loc.gov/resource/agc.7a01205/",
  },
  {
    src: "/archival/14.webp",
    headline: "\"YOUR OWN HOME NEWSPAPER\" DAILY STAR ROUTE",
    date: "July 2018",
    caption:
      "The Daily Star division delivers personalized editions to each subscriber's device. The truck's slogan has proven oddly prescient. The driver has asked how he is expected to reach the Scandinavian routes by morning but has been told to simply drive faster.",
    url: "https://www.wisconsinhistory.org/Records/Image/IM133266",
  },
  {
    src: "/archival/15.webp",
    headline: "\"THE WORLD'S GREATEST NEWSPAPER\" DEPARTS FOR OVERSEAS",
    date: "November 2023",
    caption:
      "The driver surveys the morning load before departing for overseas distribution. The sign reads \"The World's Greatest Newspaper,\" which the international subscribers have apparently taken literally. The route now extends to three continents. The driver has not been home in some time.",
    url: "https://www.wisconsinhistory.org/Records/Image/IM9644",
  },
  {
    src: "/archival/16.webp",
    headline: "SPORTS EDITION COURIER, NEWARK EVENING ROUTE",
    date: "February 2019",
    caption:
      "The evening sports feeds require their own dedicated truck and driver. The cab has no doors, which the driver notes is a problem during the transatlantic crossing. Management has classified this as a feature rather than a defect.",
    url: "https://www.wisconsinhistory.org/Records/Image/IM132052",
  },
  {
    src: "/archival/17.webp",
    headline: "PAPER BOY FLEET STANDS READY AT PIER 42",
    date: "August 2025",
    caption:
      "The full morning fleet assembles at Pier 42 for the global distribution run. The Kindle routes go by email. The Kobo routes sync through Google Drive. The remaining continental editions are loaded by hand. Several drivers have questioned the logistics but none have quit.",
    url: "https://www.wisconsinhistory.org/Records/Image/IM133848",
  },
  {
    src: "/archival/18.webp",
    headline: "MORNING EDITIONS UNLOADED AT THE EASTERN DEPOT",
    date: "May 2021",
    caption:
      "The overnight compilation run arrives at the eastern depot for final sorting. Each bound EPUB is separated by device type and delivery method before dispatch. The driver has been making this run alone since his partner transferred to the reMarkable division.",
    url: "https://www.wisconsinhistory.org/Records/Image/IM88815",
  },
  {
    src: "/archival/19.webp",
    headline: "THE ST. LOUIS MORNING RUN",
    date: "October 2024",
    caption:
      "The morning truck departs the loading dock before dawn. The overnight crew watches it leave with what witnesses describe as visible relief. This single vehicle handles all Central Time Zone deliveries, a fact that management considers efficient and the driver considers unreasonable.",
    url: "https://www.wisconsinhistory.org/Records/Image/IM63203",
  },
];

// All 19 main stories in one pool, shuffled with a hardcoded permutation.
// Odd indices → left column, even indices → right column (mixed across both).
const ALL_STORIES: ArchivalStory[] = [...LEFT_STORIES, ...RIGHT_STORIES];
const STORY_SHUFFLE = [4, 11, 0, 16, 7, 13, 2, 18, 5, 9, 14, 1, 8, 17, 3, 12, 6, 15, 10];
const SHUFFLED_STORIES = STORY_SHUFFLE.map((i) => ALL_STORIES[i]);
const COLUMN_LEFT = SHUFFLED_STORIES.filter((_, i) => i % 2 === 0);
const COLUMN_RIGHT = SHUFFLED_STORIES.filter((_, i) => i % 2 === 1);

const EASTER_EGG_STORIES: ArchivalStory[] = [
  {
    src: "/archival/20.webp",
    headline: "Breaking News!",
    date: "",
    caption: "There were easter egg hunts at the White House in the 20s.",
    url: "https://www.loc.gov/resource/hec.30890/",
  },
  {
    src: "/archival/21.webp",
    headline: "Paper Boy gives you an egg for reaching the bottom.",
    date: "",
    caption: "",
    url: "https://www.loc.gov/resource/cph.3c31864/",
  },
];

const STRIP_STORIES: ArchivalStory[] = [...SHUFFLED_STORIES, ...EASTER_EGG_STORIES];

/* Landing page */

export default function LandingPage() {
  return (
    <div className="min-h-screen bg-newsprint page-vignette">
      {/* Content wrapper: clips archival columns to content height */}
      <div className="relative xl:overflow-hidden">
        {/* Desktop archival image columns (xl+) */}
        <ArchivalColumn stories={COLUMN_LEFT} side="left" />
        <ArchivalColumn stories={COLUMN_RIGHT} side="right" />

        {/* Center content (same structure as onboarding) */}
        <div className="relative z-10 mx-auto flex max-w-4xl px-6 py-12">
          {/* Left margin decoration */}
          <aside
            className="hidden w-24 shrink-0 lg:block"
            aria-hidden="true"
          >
            <MarginDecoration side="left" />
          </aside>

          <main className="mx-auto flex w-full max-w-2xl flex-col px-0 sm:px-6">
            {/* Masthead */}
            <NewspaperMasthead
              subtitle="Your news, compiled overnight. On your e-reader by morning."
              showDateline
            />

            {/* How it works */}
            <section className="mt-16">
              <div className="ornamental-divider" />
              <h2 className="ink-print small-caps mb-8 text-center font-display text-xl font-bold uppercase tracking-wider text-ink">
                How It Works
              </h2>
              <div className="grid grid-cols-1 gap-8 sm:grid-cols-3">
                {[
                  {
                    step: "1",
                    title: "Choose Sources",
                    description:
                      "Pick from curated sources or add your own.",
                  },
                  {
                    step: "2",
                    title: "Built Overnight",
                    description:
                      "Every morning we fetch your news and compile a beautiful EPUB.",
                  },
                  {
                    step: "3",
                    title: "Read on E-Reader",
                    description:
                      "Delivered to your Kindle, Kobo, reMarkable, phone, or tablet before you wake up.",
                  },
                ].map((item) => (
                  <div key={item.step} className="text-center">
                    <div className="newsprint-card mx-auto mb-3 flex h-10 w-10 items-center justify-center overflow-hidden border-2 border-ink font-mono text-sm font-bold text-ink">
                      {item.step}
                    </div>
                    <h3 className="ink-print font-headline text-base font-bold text-ink">
                      {item.title}
                    </h3>
                    <p className="mt-2 mx-auto max-w-[13rem] font-body text-sm italic text-caption text-balance sm:max-w-none">
                      {item.description}
                    </p>
                  </div>
                ))}
              </div>
            </section>

            {/* CTA */}
            <section className="mt-16 text-center">
              <div className="ornamental-divider" />
              <p className="ink-print mb-6 font-headline text-base italic text-caption">
                Free. Open source. No ads. No tracking.
              </p>
              <Link
                href="/onboarding"
                className="letterpress inline-flex items-center bg-edition-red px-8 py-3 font-body text-sm uppercase tracking-wider text-newsprint transition-colors hover:bg-edition-red/90"
              >
                Get Started
              </Link>
              <p className="mt-3 font-body text-xs italic text-caption">
                Set up in under 2 minutes
              </p>
              <p className="mt-6 font-body text-sm text-caption">
                Already have an account?{" "}
                <Link
                  href="/login"
                  className="underline hover:no-underline"
                >
                  Sign in
                </Link>
              </p>
              <p className="mt-4 font-body text-xs text-caption/60">
                <Link
                  href="/privacy"
                  className="underline hover:no-underline"
                >
                  Privacy
                </Link>
                {" · "}
                <Link
                  href="/terms"
                  className="underline hover:no-underline"
                >
                  Terms
                </Link>
              </p>
            </section>
          </main>

          {/* Right margin decoration */}
          <aside
            className="hidden w-24 shrink-0 lg:block"
            aria-hidden="true"
          >
            <MarginDecoration side="right" />
          </aside>
        </div>
      </div>

      {/* Non-xl archival stories — horizontal scrolling strip */}
      <div className="xl:hidden pb-16">
        <div className="mx-auto max-w-sm px-6">
          <div className="ornamental-divider" />
          <div className="mb-6 text-center">
            <h2 className="ink-bleed font-display text-4xl font-black uppercase tracking-[0.12em] text-ink">
              The PB Times
            </h2>
            <p className="mt-0.5 font-typewriter text-[9px] uppercase tracking-[0.25em] text-caption/50">
              Archival Edition
            </p>
            <div className="mx-auto mt-2 h-[2px] w-20 bg-ink/25" />
          </div>
        </div>
        <ArchivalStrip stories={STRIP_STORIES} />
      </div>
    </div>
  );
}
