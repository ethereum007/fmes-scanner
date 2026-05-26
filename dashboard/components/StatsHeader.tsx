import { WinRate30d } from "@/lib/supabase";

export function StatsHeader({
  winRate,
  activeSetups,
  totalScans,
}: {
  winRate: WinRate30d | null;
  activeSetups: number;
  totalScans: number;
}) {
  const cards = [
    {
      label: "Active setups",
      value: activeSetups,
      sub: "pending + live",
    },
    {
      label: "30-day win rate",
      value:
        winRate?.win_rate_pct !== null && winRate?.win_rate_pct !== undefined
          ? `${winRate.win_rate_pct}%`
          : "—",
      sub:
        winRate && winRate.total_closed > 0
          ? `${winRate.wins}W / ${winRate.losses}L`
          : "no closed trades yet",
    },
    {
      label: "30-day expectancy",
      value:
        winRate?.expectancy_r !== null && winRate?.expectancy_r !== undefined
          ? `${winRate.expectancy_r > 0 ? "+" : ""}${winRate.expectancy_r}R`
          : "—",
      sub: "per trade @ 2.45R reward",
    },
    {
      label: "Scans logged",
      value: totalScans,
      sub: "all-time",
    },
  ];

  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
      {cards.map((c) => (
        <div
          key={c.label}
          className="rounded-lg border border-white/5 bg-white/[0.02] p-4"
        >
          <div className="text-xs uppercase tracking-wide text-foreground/40">
            {c.label}
          </div>
          <div className="mt-1 text-2xl font-semibold tabular-nums">
            {c.value}
          </div>
          <div className="text-xs text-foreground/40 mt-1">{c.sub}</div>
        </div>
      ))}
    </div>
  );
}
