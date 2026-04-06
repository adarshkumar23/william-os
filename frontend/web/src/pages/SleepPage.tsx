import { format } from "date-fns";
import { useEffect, useMemo, useState } from "react";
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { BedDouble, Clock3, Sparkles } from "lucide-react";

import ChartWrapper from "../components/ChartWrapper";
import StatCard from "../components/StatCard";
import { api } from "../services/api";
import { SleepRecommendation, SleepRecord, SleepStats } from "../types/api";

function extractDebtHours(value: Record<string, unknown> | null) {
  if (!value) {
    return 0;
  }

  const candidates = ["sleep_debt_hours", "debt_hours", "hours", "sleep_debt"];
  for (const key of candidates) {
    const raw = value[key];
    if (typeof raw === "number") {
      return raw;
    }
    if (typeof raw === "string") {
      const parsed = Number(raw);
      if (!Number.isNaN(parsed)) {
        return parsed;
      }
    }
  }

  return 0;
}

export default function SleepPage() {
  const [history, setHistory] = useState<SleepRecord[]>([]);
  const [stats, setStats] = useState<SleepStats | null>(null);
  const [debt, setDebt] = useState<Record<string, unknown> | null>(null);
  const [recommendation, setRecommendation] = useState<SleepRecommendation | null>(null);

  const load = async () => {
    const today = format(new Date(), "yyyy-MM-dd");
    const [sleepHistory, sleepStats, sleepDebt, recommendationForToday] = await Promise.all([
      api.sleep.history({ limit: 30, offset: 0 }),
      api.sleep.stats().catch(() => null),
      api.sleep.debt().catch(() => null),
      api.sleep.recommendationByDate(today).catch(() => null),
    ]);

    setHistory(sleepHistory);
    setStats(sleepStats);
    setDebt(sleepDebt);

    if (recommendationForToday) {
      setRecommendation(recommendationForToday);
    } else {
      const generated = await api.sleep.recommendationGenerate(today).catch(() => null);
      setRecommendation(generated);
    }
  };

  useEffect(() => {
    void load();
  }, []);

  const debtHours = extractDebtHours(debt);
  const debtPercent = Math.min(Math.round((debtHours / 12) * 100), 100);

  const trendData = useMemo(
    () =>
      [...history]
        .reverse()
        .slice(0, 14)
        .map((record) => ({
          date: record.sleep_date.slice(5),
          quality: record.sleep_quality,
          hours: Number((record.sleep_duration_minutes / 60).toFixed(1)),
        })),
    [history],
  );

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-bold">Sleep Recovery</h1>
        <p className="text-sm text-[rgb(var(--text-dim))]">Quality trends, debt balance, and AI recommendations.</p>
      </header>

      <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard icon={BedDouble} label="Avg Quality" value={String(stats?.avg_quality_30d ?? "--")} trend="30 days" tone="success" />
        <StatCard icon={Clock3} label="Avg Duration" value={`${stats?.avg_duration ?? "--"} min`} trend="per night" />
        <StatCard icon={Sparkles} label="Consistency" value={`${stats?.consistency_score ?? "--"}%`} trend="circadian stability" />
        <StatCard icon={Clock3} label="Sleep Debt" value={`${debtHours.toFixed(1)} h`} trend="to recover" tone={debtHours > 3 ? "danger" : "warning"} />
      </section>

      <section className="grid gap-4 lg:grid-cols-3">
        <ChartWrapper title="Sleep quality trend" subtitle="Last 14 nights">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={trendData}>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(148,163,184,0.2)" />
              <XAxis dataKey="date" tick={{ fill: "rgb(var(--text-dim))", fontSize: 11 }} />
              <YAxis yAxisId="left" domain={[0, 10]} tick={{ fill: "rgb(var(--text-dim))", fontSize: 11 }} />
              <YAxis yAxisId="right" orientation="right" domain={[0, 12]} tick={{ fill: "rgb(var(--text-dim))", fontSize: 11 }} />
              <Tooltip />
              <Line yAxisId="left" type="monotone" dataKey="quality" stroke="rgb(var(--primary))" strokeWidth={2.5} dot={{ r: 2.5 }} />
              <Line yAxisId="right" type="monotone" dataKey="hours" stroke="rgb(var(--success))" strokeWidth={2.5} dot={{ r: 2.5 }} />
            </LineChart>
          </ResponsiveContainer>
        </ChartWrapper>

        <article className="card p-4 lg:col-span-1">
          <h2 className="text-lg font-semibold">Debt meter</h2>
          <p className="mt-1 text-sm text-[rgb(var(--text-dim))]">0h means fully recovered.</p>
          <div className="mt-4 rounded-full bg-[rgb(var(--bg-muted))] p-1">
            <div
              className="h-4 rounded-full bg-gradient-to-r from-emerald-400 via-amber-400 to-rose-500 transition-all"
              style={{ width: `${debtPercent}%` }}
            />
          </div>
          <p className="mt-2 text-xs text-[rgb(var(--text-dim))]">{debtPercent}% of a 12-hour recovery threshold.</p>

          <div className="mt-6 rounded-xl bg-[rgb(var(--bg-muted))] p-3 text-sm">
            <p className="font-medium">Recommended bedtime</p>
            <p className="data-font text-xl font-semibold">{recommendation?.recommended_bedtime ?? "--:--"}</p>
            <p className="mt-2 text-xs text-[rgb(var(--text-dim))]">Wake: {recommendation?.recommended_wake_time ?? "--:--"}</p>
          </div>

          <button
            type="button"
            onClick={() => void api.sleep.recommendationGenerate(format(new Date(), "yyyy-MM-dd")).then(setRecommendation)}
            className="mt-4 rounded-xl bg-[rgb(var(--primary))] px-3 py-2 text-sm font-semibold text-white"
          >
            Refresh recommendation
          </button>
        </article>
      </section>
    </div>
  );
}
