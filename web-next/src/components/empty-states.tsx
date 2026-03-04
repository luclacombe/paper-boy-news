const EMPTY_STATES: Record<string, { headline: string; caption: string }> = {
  no_sources: {
    headline: "Your newsstand is empty",
    caption: "Add some RSS feeds to get started.",
  },
  no_editions: {
    headline: "No editions yet",
    caption: "Create your first edition from the Home page.",
  },
  no_newsletters: {
    headline: "No newsletters received",
    caption: "Newsletter support is coming soon.",
  },
  no_history: {
    headline: "No editions yet",
    caption: "Your past editions will appear here.",
  },
};

interface EmptyStateProps {
  stateKey: keyof typeof EMPTY_STATES;
}

export function EmptyState({ stateKey }: EmptyStateProps) {
  const state = EMPTY_STATES[stateKey];
  if (!state) return null;

  return (
    <div className="py-16 text-center">
      <h3 className="font-headline text-lg font-bold text-ink">
        {state.headline}
      </h3>
      <p className="mt-2 font-body text-sm text-caption">{state.caption}</p>
    </div>
  );
}
