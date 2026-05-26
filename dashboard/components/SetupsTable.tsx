import { Setup } from "@/lib/supabase";
import { cleanSymbol, cn, fmtPrice, timeAgo } from "@/lib/utils";

const STATUS_BADGE: Record<Setup["status"], { label: string; cls: string }> = {
  pending: { label: "⏳ Pending", cls: "text-foreground/70 bg-white/5" },
  live: { label: "🔵 Live", cls: "text-cyan-300 bg-cyan-500/10" },
  won: { label: "✅ Won", cls: "text-emerald-300 bg-emerald-500/10" },
  lost: { label: "❌ Lost", cls: "text-rose-300 bg-rose-500/10" },
};

export function SetupsTable({ setups }: { setups: Setup[] }) {
  if (!setups || setups.length === 0) {
    return (
      <div className="rounded-lg border border-white/5 bg-white/[0.02] p-8 text-center text-foreground/40">
        No setups yet. Daily scans run weekdays at 4 PM IST — check back after market close.
      </div>
    );
  }

  return (
    <div className="overflow-x-auto rounded-lg border border-white/5">
      <table className="w-full text-sm">
        <thead className="bg-white/[0.03] text-foreground/50 uppercase text-xs tracking-wide">
          <tr>
            <th className="text-left px-3 py-2 font-medium">Symbol</th>
            <th className="text-left px-3 py-2 font-medium">Dir</th>
            <th className="text-right px-3 py-2 font-medium">Entry</th>
            <th className="text-right px-3 py-2 font-medium">SL</th>
            <th className="text-right px-3 py-2 font-medium">TP</th>
            <th className="text-right px-3 py-2 font-medium">R:R</th>
            <th className="text-right px-3 py-2 font-medium">Price</th>
            <th className="text-left px-3 py-2 font-medium">Status</th>
            <th className="text-right px-3 py-2 font-medium">Age</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-white/5">
          {setups.map((s) => {
            const dirColor =
              s.direction === "long" ? "text-emerald-400" : "text-rose-400";
            const dirArrow = s.direction === "long" ? "▲" : "▼";
            const statusInfo = STATUS_BADGE[s.status];
            return (
              <tr
                key={s.id}
                className={cn(
                  "hover:bg-white/[0.02] transition-colors",
                  s.premium && "bg-amber-500/[0.04]"
                )}
              >
                <td className="px-3 py-2 font-medium">
                  <div className="flex items-center gap-1">
                    {s.premium && <span title="Premium setup">⭐</span>}
                    <span>{cleanSymbol(s.symbol)}</span>
                  </div>
                </td>
                <td className={cn("px-3 py-2", dirColor)}>
                  {dirArrow} {s.direction.toUpperCase()}
                </td>
                <td className="px-3 py-2 text-right tabular-nums">
                  {fmtPrice(s.entry, s.symbol)}
                </td>
                <td className="px-3 py-2 text-right tabular-nums text-rose-300/80">
                  {fmtPrice(s.sl, s.symbol)}
                </td>
                <td className="px-3 py-2 text-right tabular-nums text-cyan-300/80">
                  {fmtPrice(s.tp, s.symbol)}
                </td>
                <td className="px-3 py-2 text-right tabular-nums text-foreground/60">
                  {s.rr ?? "—"}
                </td>
                <td className="px-3 py-2 text-right tabular-nums text-foreground/70">
                  {fmtPrice(s.current_price, s.symbol)}
                </td>
                <td className="px-3 py-2">
                  <span
                    className={cn(
                      "inline-block rounded px-2 py-0.5 text-xs",
                      statusInfo.cls
                    )}
                  >
                    {statusInfo.label}
                  </span>
                </td>
                <td className="px-3 py-2 text-right tabular-nums text-foreground/50 text-xs">
                  {s.bar_age}d
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
