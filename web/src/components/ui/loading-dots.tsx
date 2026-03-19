export function LoadingDots() {
  return (
    <span className="inline-flex items-baseline gap-[3px]" aria-hidden="true">
      <span className="animate-loading-dot inline-block h-[3px] w-[3px] rounded-full bg-current" />
      <span className="animate-loading-dot inline-block h-[3px] w-[3px] rounded-full bg-current [animation-delay:150ms]" />
      <span className="animate-loading-dot inline-block h-[3px] w-[3px] rounded-full bg-current [animation-delay:300ms]" />
    </span>
  );
}
