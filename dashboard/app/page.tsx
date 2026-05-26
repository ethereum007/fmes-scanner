import { SetupsTable } from "@/components/SetupsTable";
import { StatsHeader } from "@/components/StatsHeader";
import { supabase, Setup, WinRate30d } from "@/lib/supabase";

export const revalidate = 60; // ISR: refresh every minute

async function getActiveSetups(): Promise<Setup[]> {
  const { data, error } = await supabase
    .from("setups")
    .select("*")
    .in("status", ["pending", "live"])
    .order("premium", { ascending: false })
    .order("bar_age", { ascending: true })
    .limit(100);
  if (error) {
    console.error("[setups] read error:", error);
    return [];
  }
  return (data as Setup[]) ?? [];
}

async function getWinRate(): Promise<WinRate30d | null> {
  const { data, error } = await supabase
    .from("v_win_rate_30d")
    .select("*")
    .limit(1)
    .single();
  if (error) {
    console.warn("[win_rate] view not available:", error.message);
    return null;
  }
  return data as WinRate30d;
}

async function getScanCount(): Promise<number> {
  const { count, error } = await supabase
    .from("scans")
    .select("*", { count: "exact", head: true });
  if (error) return 0;
  return count ?? 0;
}

export default async function Home() {
  const [setups, winRate, scanCount] = await Promise.all([
    getActiveSetups(),
    getWinRate(),
    getScanCount(),
  ]);

  const premium = setups.filter((s) => s.premium);
  const regular = setups.filter((s) => !s.premium);

  return (
    <div className="space-y-8">
      <StatsHeader
        winRate={winRate}
        activeSetups={setups.length}
        totalScans={scanCount}
      />

      {premium.length > 0 && (
        <section>
          <h2 className="text-sm uppercase tracking-wider text-amber-300/80 mb-3 flex items-center gap-2">
            <span>⭐</span> Premium setups
            <span className="text-foreground/40 normal-case font-normal">
              ({premium.length})
            </span>
          </h2>
          <SetupsTable setups={premium} />
        </section>
      )}

      {regular.length > 0 && (
        <section>
          <h2 className="text-sm uppercase tracking-wider text-foreground/60 mb-3">
            Other active setups
            <span className="ml-2 text-foreground/40 normal-case font-normal">
              ({regular.length})
            </span>
          </h2>
          <SetupsTable setups={regular} />
        </section>
      )}

      {setups.length === 0 && <SetupsTable setups={[]} />}

      <section className="mt-8 rounded-lg border border-white/5 bg-white/[0.02] p-4">
        <h3 className="text-sm font-medium mb-2">How to read this page</h3>
        <ul className="text-xs text-foreground/60 space-y-1 list-disc list-inside">
          <li>
            <strong className="text-foreground/80">⭐ Premium</strong> = all 3 quality filters passed (HTF trend alignment + LQ+ confluence + volume gap). Highest conviction.
          </li>
          <li>
            <strong className="text-foreground/80">⏳ Pending</strong> = limit order at Entry has not yet filled — set the order now.
          </li>
          <li>
            <strong className="text-foreground/80">🔵 Live</strong> = entry filled, position is open. SL/TP not yet hit.
          </li>
          <li>
            Risk 0.5–1% per trade. SL is at Fib 1, TP at Fib 0 (2.45R) by design.
          </li>
          <li>
            Scanner runs daily at 4 PM IST weekdays. Setups beyond 10 bars age are filtered out.
          </li>
        </ul>
      </section>
    </div>
  );
}
