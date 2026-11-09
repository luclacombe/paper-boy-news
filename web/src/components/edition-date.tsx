"use client";

import { useSyncExternalStore } from "react";
import { formatDatelineDate } from "@/lib/edition-date";

const subscribe = () => () => {};

/**
 * Today's date in the viewer's timezone.
 *
 * Marketing pages are statically rendered, so a date computed on the server
 * is frozen at build/revalidate time. The server snapshot (`serverDate`)
 * is used for the HTML and hydration; React then re-renders with the
 * browser's own date, without a hydration mismatch.
 */
export function EditionDate({ serverDate }: { serverDate: string }) {
  const date = useSyncExternalStore(
    subscribe,
    () => formatDatelineDate(),
    () => serverDate
  );
  return <span>{date}</span>;
}
