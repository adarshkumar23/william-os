import { Brain, ChevronDown, Pill, Send, Sunrise } from "lucide-react";

import { MorningBriefing } from "../types/api";

type Props = {
  briefing: MorningBriefing | null;
  loading: boolean;
  sending: boolean;
  onSendNow: () => Promise<void>;
};

function listOrFallback(items: string[], fallback: string) {
  return items.length > 0 ? items : [fallback];
}

function toMoverText(item: Record<string, unknown>) {
  const symbol = String(item.symbol ?? item.ticker ?? "-");
  const change =
    item.change_pct ?? item.change_percent ?? item.pnl_pct ?? item.unrealized_pnl_pct ?? item.return_pct;
  const changeNum = typeof change === "number" ? change : Number(change ?? 0);
  const signed = Number.isFinite(changeNum) ? `${changeNum >= 0 ? "+" : ""}${changeNum.toFixed(2)}%` : "N/A";
  return `${symbol} (${signed})`;
}

export default function MorningBriefingCard({ briefing, loading, sending, onSendNow }: Props) {
  return (
    <section className="card overflow-hidden">
      <div className="bg-gradient-to-r from-sky-500/15 via-emerald-400/10 to-amber-400/15 p-5">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.2em] text-[rgb(var(--text-dim))]">Morning OS Briefing</p>
            <h2 className="mt-1 text-2xl font-bold">Your day, synthesized before it starts</h2>
            <p className="mt-1 text-sm text-[rgb(var(--text-dim))]">Wake + 5 min unified snapshot across schedule, health, habits, study, and markets.</p>
          </div>
          <button
            type="button"
            onClick={() => void onSendNow()}
            disabled={loading || sending}
            className="inline-flex items-center gap-2 rounded-xl bg-[rgb(var(--primary))] px-3 py-2 text-sm font-semibold text-white disabled:cursor-not-allowed disabled:opacity-60"
          >
            <Send className="h-4 w-4" />
            {sending ? "Sending..." : "Send now"}
          </button>
        </div>
      </div>

      {loading && !briefing ? (
        <div className="p-5 text-sm text-[rgb(var(--text-dim))]">Building briefing context...</div>
      ) : briefing ? (
        <div className="grid gap-4 p-5 lg:grid-cols-3">
          <div className="rounded-2xl border border-[rgb(var(--border))] bg-[rgb(var(--bg-muted))] p-4 lg:col-span-3">
            <p className="mb-1 flex items-center gap-2 text-xs font-semibold uppercase tracking-widest text-[rgb(var(--text-dim))]">
              <Brain className="h-4 w-4" /> AI recommendation of the day
            </p>
            <p className="text-base font-medium leading-relaxed">{briefing.ai_recommendation_of_day}</p>
            <p className="mt-2 text-xs text-[rgb(var(--text-dim))]">Life score: {briefing.life_score.score.toFixed(1)} / 100</p>
          </div>

          <details className="rounded-xl border border-[rgb(var(--border))] bg-[rgb(var(--bg-elevated))] p-3" open>
            <summary className="flex cursor-pointer list-none items-center justify-between gap-2 text-sm font-semibold">
              <span className="inline-flex items-center gap-2"><Sunrise className="h-4 w-4" /> Schedule (Top 5)</span>
              <ChevronDown className="h-4 w-4" />
            </summary>
            <div className="mt-3 space-y-2 text-sm">
              {briefing.today_schedule.length > 0 ? (
                briefing.today_schedule.map((item) => (
                  <p key={item.id} className="rounded-lg bg-[rgb(var(--bg-muted))] p-2">
                    <span className="font-semibold">{item.start_time}</span> {item.title}
                  </p>
                ))
              ) : (
                <p className="text-[rgb(var(--text-dim))]">No blocks scheduled.</p>
              )}
            </div>
          </details>

          <details className="rounded-xl border border-[rgb(var(--border))] bg-[rgb(var(--bg-elevated))] p-3" open>
            <summary className="flex cursor-pointer list-none items-center justify-between gap-2 text-sm font-semibold">
              <span>Priority habits</span>
              <ChevronDown className="h-4 w-4" />
            </summary>
            <div className="mt-3 space-y-2 text-sm">
              {briefing.priority_habits.length > 0 ? (
                briefing.priority_habits.map((item) => (
                  <p key={item.id} className="rounded-lg bg-[rgb(var(--bg-muted))] p-2">
                    {item.name} {item.preferred_time ? `(${item.preferred_time})` : ""}
                  </p>
                ))
              ) : (
                <p className="text-[rgb(var(--text-dim))]">All due habits are completed.</p>
              )}
            </div>
          </details>

          <details className="rounded-xl border border-[rgb(var(--border))] bg-[rgb(var(--bg-elevated))] p-3" open>
            <summary className="flex cursor-pointer list-none items-center justify-between gap-2 text-sm font-semibold">
              <span className="inline-flex items-center gap-2"><Pill className="h-4 w-4" /> Missed medicines (24h)</span>
              <ChevronDown className="h-4 w-4" />
            </summary>
            <div className="mt-3 space-y-2 text-sm">
              {briefing.missed_medicines.length > 0 ? (
                briefing.missed_medicines.map((item) => (
                  <p key={`${item.medicine_name}-${item.log_date}-${item.scheduled_time}`} className="rounded-lg bg-[rgb(var(--bg-muted))] p-2">
                    {item.medicine_name} at {item.scheduled_time}
                  </p>
                ))
              ) : (
                <p className="text-[rgb(var(--text-dim))]">No misses in the last 24 hours.</p>
              )}
            </div>
          </details>

          <details className="rounded-xl border border-[rgb(var(--border))] bg-[rgb(var(--bg-elevated))] p-3 lg:col-span-2" open>
            <summary className="flex cursor-pointer list-none items-center justify-between gap-2 text-sm font-semibold">
              <span>Upcoming deadlines</span>
              <ChevronDown className="h-4 w-4" />
            </summary>
            <div className="mt-3 space-y-2 text-sm">
              {briefing.upcoming_deadlines.length > 0 ? (
                briefing.upcoming_deadlines.map((item, index) => (
                  <p key={`${item.source}-${item.due_date}-${index}`} className="rounded-lg bg-[rgb(var(--bg-muted))] p-2">
                    <span className="font-semibold">{item.due_date}</span> {item.title}
                  </p>
                ))
              ) : (
                <p className="text-[rgb(var(--text-dim))]">No upcoming deadlines in the next 7 days.</p>
              )}
            </div>
          </details>

          <details className="rounded-xl border border-[rgb(var(--border))] bg-[rgb(var(--bg-elevated))] p-3" open>
            <summary className="flex cursor-pointer list-none items-center justify-between gap-2 text-sm font-semibold">
              <span>Market movement</span>
              <ChevronDown className="h-4 w-4" />
            </summary>
            <div className="mt-3 space-y-2 text-sm">
              {listOrFallback(
                (briefing.market_watchlist_movement.top_gainers ?? []).map((item) => toMoverText(item)),
                "No top gainers",
              ).map((line) => (
                <p key={`gain-${line}`} className="rounded-lg bg-[rgb(var(--bg-muted))] p-2">{line}</p>
              ))}
              {listOrFallback(
                (briefing.market_watchlist_movement.top_losers ?? []).map((item) => toMoverText(item)),
                "No top losers",
              ).map((line) => (
                <p key={`loss-${line}`} className="rounded-lg bg-[rgb(var(--bg-muted))] p-2">{line}</p>
              ))}
            </div>
          </details>

          <details className="rounded-xl border border-[rgb(var(--border))] bg-[rgb(var(--bg-elevated))] p-3 lg:col-span-3" open>
            <summary className="flex cursor-pointer list-none items-center justify-between gap-2 text-sm font-semibold">
              <span>Energy prediction</span>
              <ChevronDown className="h-4 w-4" />
            </summary>
            <div className="mt-3 grid gap-2 text-sm md:grid-cols-3">
              <p className="rounded-lg bg-[rgb(var(--bg-muted))] p-2">
                Peak: {briefing.energy_prediction?.peak_hours?.join(", ") || "N/A"}
              </p>
              <p className="rounded-lg bg-[rgb(var(--bg-muted))] p-2">
                Low: {briefing.energy_prediction?.low_hours?.join(", ") || "N/A"}
              </p>
              <p className="rounded-lg bg-[rgb(var(--bg-muted))] p-2">
                Suggestions: {(briefing.energy_prediction?.suggestions || []).join(" | ") || "N/A"}
              </p>
            </div>
          </details>
        </div>
      ) : (
        <div className="p-5 text-sm text-[rgb(var(--text-dim))]">No briefing available yet.</div>
      )}
    </section>
  );
}
