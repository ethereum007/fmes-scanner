import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function fmtPrice(n: number | null | undefined, ticker?: string): string {
  if (n === null || n === undefined || !isFinite(n)) return "—";
  // Use ₹ for NSE tickers, $ for everything else (rough heuristic)
  const symbol = ticker?.endsWith(".NS") ? "₹" : "";
  return symbol + n.toLocaleString(undefined, { maximumFractionDigits: 2 });
}

export function cleanSymbol(s: string): string {
  return s.replace(/\.NS$/, "").replace(/=X$/, "");
}

export function timeAgo(iso: string): string {
  const ms = Date.now() - new Date(iso).getTime();
  const days = Math.floor(ms / 86400000);
  if (days === 0) return "today";
  if (days === 1) return "1 day ago";
  if (days < 30) return `${days} days ago`;
  const months = Math.floor(days / 30);
  return `${months} mo ago`;
}
