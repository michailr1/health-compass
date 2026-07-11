import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

/**
 * Format a date-only string (YYYY-MM-DD) as DD.MM.YYYY without ever going
 * through Date parsing: `new Date("2026-07-11")` is interpreted as UTC
 * midnight and shifts the calendar day in negative-offset timezones.
 */
export function formatDateOnlyRu(value: string): string {
  const match = /^(\d{4})-(\d{2})-(\d{2})/.exec(value);
  if (!match) return value;
  return `${match[3]}.${match[2]}.${match[1]}`;
}

/** Today's calendar date in the user's local timezone as YYYY-MM-DD. */
export function localDateOnlyISO(date: Date = new Date()): string {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}
