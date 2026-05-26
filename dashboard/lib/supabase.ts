import { createClient } from "@supabase/supabase-js";

const url = process.env.NEXT_PUBLIC_SUPABASE_URL!;
const anonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!;

if (!url || !anonKey) {
  // Build-time check — surface a clear error if env is missing
  console.warn(
    "Missing NEXT_PUBLIC_SUPABASE_URL or NEXT_PUBLIC_SUPABASE_ANON_KEY"
  );
}

export const supabase = createClient(url, anonKey, {
  auth: { persistSession: false },
});

export type Setup = {
  id: number;
  symbol: string;
  direction: "long" | "short";
  signal_date: string;
  bar_age: number;
  entry: number;
  sl: number;
  tp: number;
  tp1: number | null;
  ob_entry: number | null;
  ob_tp: number | null;
  current_price: number | null;
  status: "pending" | "live" | "won" | "lost";
  premium: boolean;
  htf_trend: string | null;
  has_lq_plus: boolean;
  risk_pct: number | null;
  reward_pct: number | null;
  rr: number | null;
  created_at: string;
};

export type Scan = {
  id: number;
  run_at: string;
  universe_size: number;
  setups_found: number;
  failed_count: number;
  timeframe: string;
  universes: string[];
};

export type WinRate30d = {
  wins: number;
  losses: number;
  total_closed: number;
  win_rate_pct: number | null;
  expectancy_r: number | null;
};
