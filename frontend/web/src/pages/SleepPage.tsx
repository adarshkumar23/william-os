import { format } from "date-fns";
import { motion, useReducedMotion } from "framer-motion";
import { BedDouble, Moon } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { fadeInUp, reduceMotion, staggerContainer } from "../lib/animations";
import { api } from "../services/api";
import { SleepRecommendation, SleepRecord, SleepStats } from "../types/api";
import { AnimatedCounter, AppCard, EmptyState, ProgressRing, SectionHeader, SkeletonLoader } from "../components/ui";

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
  const [loading, setLoading] = useState(true);

  const shouldReduceMotion = useReducedMotion();
  const fadeMotion = reduceMotion(shouldReduceMotion, fadeInUp);

  const load = async () => {
    setLoading(true);
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

    setLoading(false);
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
        .slice(0, 7)
        .map((record) => ({
          date: record.sleep_date.slice(5),
          quality: record.sleep_quality,
          hours: Number((record.sleep_duration_minutes / 60).toFixed(1)),
        })),
    [history],
  );

  const onCreateStarterSleepLog = async () => {
    const wake = new Date();
    const bed = new Date(wake.getTime() - 8 * 60 * 60 * 1000);
    await api.sleep.log({
      sleep_date: format(new Date(), "yyyy-MM-dd"),
      bedtime: bed.toISOString(),
      wake_time: wake.toISOString(),
      sleep_quality: 7,
      interruptions: 0,
      source: "manual",
    });
    await load();
  };

  return (
    <div className="space-y-6">
      <SectionHeader title="Sleep" subtitle="Recovery intelligence with debt tracking and circadian guidance." />

      <motion.section variants={staggerContainer} initial="initial" animate="animate" className="grid gap-4 lg:grid-cols-3">
        <motion.div variants={fadeMotion}>
          <AppCard hover className="h-full bg-indigo-950/25">
            <p className="section-label">Sleep Score</p>
            <div className="mt-4 flex items-center justify-center">
              <ProgressRing value={Math.round(stats?.avg_quality_30d || 0) * 10} color="rgb(var(--color-info))" label="Quality" />
            </div>
          </AppCard>
        </motion.div>

        <motion.div variants={fadeMotion} className="lg:col-span-2">
          <AppCard className="bg-indigo-950/20">
            <p className="section-label">Hours Slept (avg)</p>
            <p className="mt-3 text-4xl font-bold tabular-nums text-text-primary">
              <AnimatedCounter value={Number(((stats?.avg_duration || 0) / 60).toFixed(1))} /> h
            </p>
            <p className="meta-copy mt-2">Recommended bedtime: {recommendation?.recommended_bedtime || "--:--"}</p>
          </AppCard>
        </motion.div>
      </motion.section>

      {loading ? (
        <SkeletonLoader variant="card" />
      ) : history.length === 0 ? (
        <EmptyState
          icon={<Moon className="h-6 w-6" />}
          title="No sleep records yet"
          description="Add your first sleep log to start debt and recovery tracking."
          action={
            <button
              type="button"
              onClick={() => void onCreateStarterSleepLog()}
              className="rounded-button bg-accent px-4 py-2 text-sm font-semibold text-white"
            >
              Log First Sleep
            </button>
          }
        />
      ) : (
        <>
          <AppCard className="bg-indigo-950/15">
            <p className="section-label">Sleep Debt Meter</p>
            <div className="mt-4 h-4 rounded-full bg-surface-raised">
              <div className="h-4 rounded-full bg-warning transition-all duration-700" style={{ width: `${debtPercent}%` }} />
            </div>
            <p className="meta-copy mt-2">
              <AnimatedCounter value={Number(debtHours.toFixed(1))} />h debt remaining
            </p>
          </AppCard>

          <AppCard className="bg-indigo-950/10">
            <p className="section-label">7 Day Sleep Trend</p>
            <div className="mt-4 h-60">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={trendData} margin={{ top: 5, right: 10, left: -25, bottom: 0 }}>
                  <XAxis dataKey="date" tick={{ fill: "rgb(var(--color-text-muted))", fontSize: 11 }} axisLine={false} tickLine={false} />
                  <YAxis domain={[0, 10]} tick={{ fill: "rgb(var(--color-text-muted))", fontSize: 11 }} axisLine={false} tickLine={false} />
                  <Tooltip />
                  <Line dataKey="quality" stroke="rgb(var(--color-info))" strokeWidth={2.5} dot={false} />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </AppCard>

          <AppCard>
            <p className="section-label">Recent Records</p>
            <div className="mt-4 space-y-2">
              {history.slice(0, 8).map((item) => (
                <div key={item.id} className="flex items-center justify-between rounded-lg border border-border bg-surface-raised p-3">
                  <div>
                    <p className="text-sm text-text-primary">{item.sleep_date}</p>
                    <p className="meta-copy">Quality {item.sleep_quality}/10</p>
                  </div>
                  <p className="text-sm text-text-secondary">{(item.sleep_duration_minutes / 60).toFixed(1)}h</p>
                </div>
              ))}
            </div>
          </AppCard>
        </>
      )}
    </div>
  );
}
