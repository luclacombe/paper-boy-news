"use client";

import Image from "next/image";
import { useEffect, useRef } from "react";

export interface ArchivalStory {
  src: string;
  headline: string;
  date: string;
  caption: string;
  url: string;
}

export function StoryCard({
  story,
  variant,
}: {
  story: ArchivalStory;
  variant?: "strip";
}) {
  // Strip variant: NO bg-newsprint anywhere — any opaque rectangle in a
  // GPU-composited transform layer shows a faint edge against the page bg.
  // Instead of mix-blend-mode:multiply (which needs an opaque backdrop),
  // we use sepia() in the filter chain to warm-tint whites directly.
  // overflow:clip instead of overflow:hidden avoids compositing edges.
  if (variant === "strip") {
    return (
      <a
        href={story.url}
        target="_blank"
        rel="noopener noreferrer"
        className="block pb-4"
      >
        <div className="relative h-44 w-full" style={{ overflow: "clip" }}>
          <Image
            src={story.src}
            alt={story.headline}
            fill
            sizes="240px"
            className="object-cover object-top [filter:grayscale(100%)_sepia(20%)_contrast(1.1)]"
          />
        </div>
        {story.headline ? (
          <h4 className="mt-2.5 px-2 whitespace-pre-line font-typewriter text-[11px] leading-snug tracking-wide text-ink">
            {story.headline}
          </h4>
        ) : null}
        {story.date ? (
          <p className="mt-1 px-2 font-mono text-[8px] uppercase tracking-widest text-caption/70">
            {story.date}
          </p>
        ) : null}
        {story.caption ? (
          <p className="mt-1 px-2 font-body text-[10px] leading-relaxed text-caption">
            {story.caption.split(/(\d+)/).map((part, i) =>
              /^\d+$/.test(part) ? (
                <span key={i} className="text-[1.2em]">
                  {part}
                </span>
              ) : (
                part
              )
            )}
          </p>
        ) : null}
        <p className="mt-2 px-2 font-typewriter text-[8px] uppercase tracking-widest text-caption/60">
          ✦ Continued in the Archive ✦
        </p>
      </a>
    );
  }

  return (
    <a
      href={story.url}
      target="_blank"
      rel="noopener noreferrer"
      className="block bg-newsprint px-2 py-4"
    >
      <div className="h-32 w-full" style={{ overflow: "clip" }}>
        <Image
          src={story.src}
          alt={story.headline}
          width={200}
          height={128}
          sizes="200px"
          className="h-full w-full object-cover object-top [filter:grayscale(100%)_contrast(1.1)] [mix-blend-mode:multiply]"
        />
      </div>
      {story.headline ? (
        <h4 className="mt-2.5 whitespace-pre-line font-typewriter text-[11px] leading-snug tracking-wide text-ink">
          {story.headline}
        </h4>
      ) : null}
      {story.date ? (
        <p className="mt-1 font-mono text-[8px] uppercase tracking-widest text-caption/70">
          {story.date}
        </p>
      ) : null}
      {story.caption ? (
        <p className="mt-1 font-body text-[10px] leading-relaxed text-caption">
          {story.caption.split(/(\d+)/).map((part, i) =>
            /^\d+$/.test(part) ? (
              <span key={i} className="text-[1.2em]">
                {part}
              </span>
            ) : (
              part
            )
          )}
        </p>
      ) : null}
      <p className="mt-2 font-typewriter text-[8px] uppercase tracking-widest text-caption/60">
        ✦ Continued in the Archive ✦
      </p>
    </a>
  );
}

// Normalise pixel position to (-halfH, 0] for seamless looping.
const normPos = (pos: number, half: number) => {
  pos = pos % half;
  if (pos > 0) pos -= half;
  return pos;
};

const DURATION_MS = 145_000;

export function ArchivalColumn({
  stories,
  side,
}: {
  stories: ArchivalStory[];
  side: "left" | "right";
}) {
  const doubled = [...stories, ...stories];
  const scrollRef = useRef<HTMLDivElement>(null);
  const stateRef = useRef({
    pos: 0,
    isPaused: false,
    isManual: false,
    lastTime: null as number | null,
  });
  const rafRef = useRef<number>(0);
  const resumeTimerRef = useRef<ReturnType<typeof setTimeout>>(undefined);

  useEffect(() => {
    const el = scrollRef.current;
    if (!el) return;
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;

    // Left scrolls content upward (pos increases toward 0), right scrolls down
    const direction = side === "left" ? 1 : -1;
    const state = stateRef.current;

    // Don't eagerly overwrite the SSR transform — let the first rAF read the
    // current scrollHeight and set pos atomically with the animation start.
    // This avoids a one-frame flash if scrollHeight differs at hydration time.
    let initialised = false;

    const tick = (time: number) => {
      const halfH = el.scrollHeight / 2;
      if (!initialised) {
        state.pos = side === "left" ? -halfH : 0;
        initialised = true;
      }
      if (halfH > 0 && !state.isPaused && !state.isManual) {
        if (state.lastTime !== null) {
          const delta = time - state.lastTime;
          state.pos = normPos(
            state.pos + (halfH / DURATION_MS) * direction * delta,
            halfH,
          );
        }
        state.lastTime = time;
        el.style.transform = `translateY(${state.pos}px)`;
      } else {
        state.lastTime = null;
      }
      rafRef.current = requestAnimationFrame(tick);
    };

    rafRef.current = requestAnimationFrame(tick);

    // Pause loop when tab is hidden, restart when visible
    const handleVisibility = () => {
      if (document.hidden) {
        cancelAnimationFrame(rafRef.current);
        rafRef.current = 0;
        state.lastTime = null;
      } else if (!rafRef.current) {
        state.lastTime = null;
        rafRef.current = requestAnimationFrame(tick);
      }
    };
    document.addEventListener("visibilitychange", handleVisibility);

    const aside = el.parentElement as HTMLElement;

    // Wheel: two-finger trackpad takes manual control
    const handleWheel = (e: WheelEvent) => {
      // Ignore if predominantly horizontal
      if (Math.abs(e.deltaY) <= Math.abs(e.deltaX)) return;
      e.preventDefault();

      state.isManual = true;
      state.lastTime = null;

      const halfH = el.scrollHeight / 2;
      if (halfH > 0) {
        state.pos = normPos(state.pos - e.deltaY, halfH);
        el.style.transform = `translateY(${state.pos}px)`;
      }

      clearTimeout(resumeTimerRef.current);
      resumeTimerRef.current = setTimeout(() => {
        state.isManual = false;
      }, 800);
    };

    // Touch: one-finger drag for large tablets
    let touchStartY = 0;

    const handleTouchStart = (e: TouchEvent) => {
      touchStartY = e.touches[0].clientY;
      state.isManual = true;
      state.lastTime = null;
      clearTimeout(resumeTimerRef.current);
    };

    const handleTouchMove = (e: TouchEvent) => {
      e.preventDefault();
      const deltaY = touchStartY - e.touches[0].clientY;
      touchStartY = e.touches[0].clientY;
      const halfH = el.scrollHeight / 2;
      if (halfH > 0) {
        state.pos = normPos(state.pos - deltaY, halfH);
        el.style.transform = `translateY(${state.pos}px)`;
      }
    };

    const handleTouchEnd = () => {
      clearTimeout(resumeTimerRef.current);
      resumeTimerRef.current = setTimeout(() => {
        state.isManual = false;
      }, 800);
    };

    aside.addEventListener("wheel", handleWheel, { passive: false });
    aside.addEventListener("touchstart", handleTouchStart, { passive: true });
    aside.addEventListener("touchmove", handleTouchMove, { passive: false });
    aside.addEventListener("touchend", handleTouchEnd, { passive: true });

    return () => {
      cancelAnimationFrame(rafRef.current);
      clearTimeout(resumeTimerRef.current);
      document.removeEventListener("visibilitychange", handleVisibility);
      aside.removeEventListener("wheel", handleWheel);
      aside.removeEventListener("touchstart", handleTouchStart);
      aside.removeEventListener("touchmove", handleTouchMove);
      aside.removeEventListener("touchend", handleTouchEnd);
    };
  }, [side]);

  return (
    <aside
      className="archival-slot absolute top-[10rem] bottom-[10rem] hidden w-[200px] overflow-hidden opacity-50 xl:block"
      style={{
        [side === "left" ? "left" : "right"]: "calc(25vw - 16.5rem)",
      }}
      aria-hidden="true"
    >
      <div
        ref={scrollRef}
        style={side === "left" ? { transform: "translateY(-50%)" } : undefined}
      >
        {doubled.map((story, i) => (
          <div
            key={`${story.src}-${i}`}
            className="mb-12"
            onMouseEnter={() => {
              stateRef.current.isPaused = true;
            }}
            onMouseLeave={() => {
              stateRef.current.isPaused = false;
            }}
          >
            <StoryCard story={story} />
          </div>
        ))}
      </div>
    </aside>
  );
}

const STRIP_DURATION_MS = 145_000;

export function ArchivalStrip({ stories }: { stories: ArchivalStory[] }) {
  const innerRef = useRef<HTMLDivElement>(null);
  const stateRef = useRef({
    pos: 0,
    isPaused: false,
    isManual: false,
    lastTime: null as number | null,
  });
  const rafRef = useRef<number>(0);
  const resumeTimerRef = useRef<ReturnType<typeof setTimeout>>(undefined);

  const doubled = [...stories, ...stories];

  useEffect(() => {
    const el = innerRef.current;
    if (!el) return;
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;

    const state = stateRef.current;
    let initialised = false;

    const tick = (time: number) => {
      const halfW = el.scrollWidth / 2;
      if (!initialised) {
        state.pos = -halfW;
        initialised = true;
      }
      if (halfW > 0 && !state.isPaused && !state.isManual) {
        if (state.lastTime !== null) {
          const delta = time - state.lastTime;
          state.pos = normPos(
            state.pos + (halfW / STRIP_DURATION_MS) * delta,
            halfW,
          );
        }
        state.lastTime = time;
        el.style.transform = `translateX(${state.pos}px)`;
      } else {
        state.lastTime = null;
      }
      rafRef.current = requestAnimationFrame(tick);
    };

    rafRef.current = requestAnimationFrame(tick);

    const handleVisibility = () => {
      if (document.hidden) {
        cancelAnimationFrame(rafRef.current);
        rafRef.current = 0;
        state.lastTime = null;
      } else if (!rafRef.current) {
        state.lastTime = null;
        rafRef.current = requestAnimationFrame(tick);
      }
    };
    document.addEventListener("visibilitychange", handleVisibility);

    const wrapper = el.parentElement as HTMLElement;

    // Mouse drag: manual control
    let isDragging = false;
    let startX = 0;

    const onMouseDown = (e: MouseEvent) => {
      isDragging = true;
      startX = e.clientX;
      state.isManual = true;
      state.lastTime = null;
      wrapper.style.cursor = "grabbing";
      wrapper.style.userSelect = "none";
      clearTimeout(resumeTimerRef.current);
    };

    const onMouseMove = (e: MouseEvent) => {
      if (!isDragging) return;
      const halfW = el.scrollWidth / 2;
      if (halfW > 0) {
        state.pos = normPos(state.pos - (e.clientX - startX), halfW);
        el.style.transform = `translateX(${state.pos}px)`;
      }
      startX = e.clientX;
    };

    const onMouseUp = () => {
      if (!isDragging) return;
      isDragging = false;
      wrapper.style.cursor = "grab";
      wrapper.style.userSelect = "";
      resumeTimerRef.current = setTimeout(() => {
        state.isManual = false;
      }, 800);
    };

    // Touch drag
    let touchStartX = 0;

    const onTouchStart = (e: TouchEvent) => {
      touchStartX = e.touches[0].clientX;
      state.isManual = true;
      state.lastTime = null;
      clearTimeout(resumeTimerRef.current);
    };

    const onTouchMove = (e: TouchEvent) => {
      const deltaX = touchStartX - e.touches[0].clientX;
      touchStartX = e.touches[0].clientX;
      const halfW = el.scrollWidth / 2;
      if (halfW > 0) {
        state.pos = normPos(state.pos - deltaX, halfW);
        el.style.transform = `translateX(${state.pos}px)`;
      }
    };

    const onTouchEnd = () => {
      resumeTimerRef.current = setTimeout(() => {
        state.isManual = false;
      }, 800);
    };

    wrapper.addEventListener("mousedown", onMouseDown);
    window.addEventListener("mousemove", onMouseMove);
    window.addEventListener("mouseup", onMouseUp);
    wrapper.addEventListener("touchstart", onTouchStart, { passive: true });
    wrapper.addEventListener("touchmove", onTouchMove, { passive: true });
    wrapper.addEventListener("touchend", onTouchEnd, { passive: true });

    return () => {
      cancelAnimationFrame(rafRef.current);
      clearTimeout(resumeTimerRef.current);
      document.removeEventListener("visibilitychange", handleVisibility);
      wrapper.removeEventListener("mousedown", onMouseDown);
      window.removeEventListener("mousemove", onMouseMove);
      window.removeEventListener("mouseup", onMouseUp);
      wrapper.removeEventListener("touchstart", onTouchStart);
      wrapper.removeEventListener("touchmove", onTouchMove);
      wrapper.removeEventListener("touchend", onTouchEnd);
    };
  }, []);

  return (
    <div
      className="relative"
      style={{
        cursor: "grab",
        overflow: "clip",
        WebkitMaskImage:
          "linear-gradient(to right, transparent, black 18%, black 82%, transparent)",
        maskImage:
          "linear-gradient(to right, transparent, black 18%, black 82%, transparent)",
      }}
    >
      <div
        ref={innerRef}
        className="flex gap-14 py-4"
        style={{ transform: "translateX(-50%)" }}
        onMouseEnter={() => {
          stateRef.current.isPaused = true;
        }}
        onMouseLeave={() => {
          stateRef.current.isPaused = false;
        }}
      >
        {doubled.map((story, i) => (
          <div key={`${story.src}-${i}`} className="w-60 shrink-0">
            <StoryCard story={story} variant="strip" />
          </div>
        ))}
      </div>
    </div>
  );
}
