import { cn } from "@/lib/utils";

interface NewspaperMastheadProps {
  subtitle?: string;
  showDateline?: boolean;
  compact?: boolean;
  className?: string;
}

/** Wrap punctuation in small-caps text so it doesn't look oversized */
function scalePunctuation(text: string): React.ReactNode[] {
  return text.split(/([.,;:!?])/).map((part, i) =>
    /^[.,;:!?]$/.test(part) ? (
      <span key={i} className="small-caps-punct">{part}</span>
    ) : (
      part
    )
  );
}

function formatDate(): string {
  const now = new Date();
  return now.toLocaleDateString("en-US", {
    weekday: "long",
    year: "numeric",
    month: "long",
    day: "numeric",
  });
}

export function NewspaperMasthead({
  subtitle,
  showDateline = true,
  compact = false,
  className,
}: NewspaperMastheadProps) {
  return (
    <div className={cn("text-center", className)}>
      {/* Top double rule */}
      <div className="border-t-[3px] border-ink" />
      <div className="mt-[3px] border-t border-ink" />

      {/* Nameplate */}
      <h1
        className={cn(
          "ink-bleed font-display font-black uppercase text-ink",
          compact
            ? "py-3 text-2xl tracking-[0.15em] sm:text-3xl"
            : "py-4 text-3xl tracking-[0.15em] sm:py-6 sm:text-5xl sm:tracking-[0.2em]"
        )}
      >
        Paper Boy
      </h1>

      {/* Motto */}
      {subtitle && (
        <p className="small-caps -mt-2 pb-3 font-typewriter text-sm text-caption sm:-mt-3 sm:pb-4">
          {scalePunctuation(subtitle)}
        </p>
      )}

      {/* Dateline bar */}
      {showDateline && (
        <>
          <div className="border-t border-ink" />
          <div className="flex items-center justify-center gap-2 px-2 py-1.5 font-mono text-[10px] uppercase tracking-widest text-caption sm:gap-4 sm:text-xs">
            <span className="hidden sm:inline">Vol. I</span>
            <span className="hidden sm:inline" aria-hidden="true">
              ·
            </span>
            <span>{formatDate()}</span>
            <span className="hidden sm:inline" aria-hidden="true">
              ·
            </span>
            <span className="hidden sm:inline">Morning Edition</span>
          </div>
          <div className="border-t border-ink" />
        </>
      )}

      {/* Bottom double rule */}
      <div className="mt-[3px] border-t-[3px] border-ink" />
    </div>
  );
}
