import { addDays, format } from "date-fns";
import { motion, useReducedMotion } from "framer-motion";
import {
  Activity,
  AlertTriangle,
  CalendarDays,
  Clock3,
  Flame,
  HeartPulse,
  LineChart,
  Moon,
  Sparkles,
  Target,
  Zap,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { AppCard, Badge, InsightBanner, ProgressRing, QuickActionButton, SkeletonLoader } from "../components/ui";
import { useAuth } from "../contexts/AuthContext";
import { fadeInUp, reduceMotion, staggerContainer } from "../lib/animations";
import { api } from "../services/api";
import {
  CalendarTodayResponse,
  CalendarEvent,
  CalendarSyncConflict,
  DailyPlan,
  BurnoutScorePayload,
  EnergyForecast,
  Habit,
  LifeScore,
  LifeScoreHistoryPoint,
  PredictiveWarning,
  TimelineEvent,
  WeeklyReview,
} from "../types/api";

function toDate(value: string) {
  if (value.includes("T")) {
    return new Date(value);
  }
  return new Date(`${value}T00:00:00`);
}

function mapTrendVariant(value: string) {
  if (value === "improving") {
    return "success" as const;
  }
  if (value === "declining") {
    return "danger" as const;
  }
  return "warning" as const;
}

export default function DashboardPage() {
  const [plan, setPlan] = useState<DailyPlan | null>(null);
  const [habits, setHabits] = useState<Habit[]>([]);
  const [lifeScore, setLifeScore] = useState<LifeScore | null>(null);
  const [lifeScoreHistory, setLifeScoreHistory] = useState<LifeScoreHistoryPoint[]>([]);
  const [timeline, setTimeline] = useState<TimelineEvent[]>([]);
  const [energyForecast, setEnergyForecast] = useState<EnergyForecast | null>(null);
  const [weeklyReview, setWeeklyReview] = useState<WeeklyReview | null>(null);
  const [calendarEvents, setCalendarEvents] = useState<CalendarEvent[]>([]);
  const [warnings, setWarnings] = useState<PredictiveWarning[]>([]);
  const [burnoutScore, setBurnoutScore] = useState<BurnoutScorePayload | null>(null);
  const [calendarConflicts, setCalendarConflicts] = useState<CalendarSyncConflict[]>([]);
  const [warningsExpanded, setWarningsExpanded] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const { user } = useAuth();
  const navigate = useNavigate();
  const shouldReduceMotion = useReducedMotion();
  const fadeMotion = reduceMotion(shouldReduceMotion, fadeInUp);

  const load = async () => {
    setLoading(true);
    setError("");

    try {
      const today = format(new Date(), "yyyy-MM-dd");
      const todayPlan = (await api.scheduler.today().catch(() => null)) as DailyPlan | null;
      const habitRows =
        (await api.habits
          .list({ active_only: true, limit: 100, offset: 0 })
          .catch(() => [] as Habit[])) as Habit[];
      const score = (await api.intelligence.lifeScore().catch(() => null)) as LifeScore | null;
      const scoreHistory =
        (await api.intelligence.lifeScoreHistory(45).catch(
          () => [] as LifeScoreHistoryPoint[],
        )) as LifeScoreHistoryPoint[];
      const timelineRows =
        (await api.intelligence.timeline(30).catch(() => [] as TimelineEvent[])) as TimelineEvent[];
      const energy = (await api.fitness.energyByDate(today).catch(() => null)) as EnergyForecast | null;
      const review =
        (await api.briefing.weeklyReview().catch(() => null as WeeklyReview | null)) as
          WeeklyReview | null;
      const calendarToday =
        (await api.calendar.today().catch(() => ({ events: [] } as CalendarTodayResponse))) as
          CalendarTodayResponse;
      const warningRows =
        (await api.intelligence.warnings().catch(() => [] as PredictiveWarning[])) as PredictiveWarning[];
      const burnout =
        (await api.intelligence.burnoutScore().catch(() => null)) as BurnoutScorePayload | null;
      const conflicts =
        (await api.calendar.syncConflicts().catch(() => ({ conflicts: [] as CalendarSyncConflict[] }))) as
          { conflicts: CalendarSyncConflict[] };

      setPlan(todayPlan);
      setHabits(habitRows);
      setLifeScore(score);
      setLifeScoreHistory(scoreHistory);
      setTimeline(timelineRows);
      setEnergyForecast(energy);
      setWeeklyReview(review);
      setCalendarEvents(calendarToday.events ?? []);
      setWarnings(warningRows);
      setBurnoutScore(burnout);
      setCalendarConflicts(conflicts.conflicts ?? []);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to load dashboard.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void load();
  }, []);

  const score = Math.round(Number(lifeScore?.score || 0));
  const todayName = String(user?.display_name || user?.full_name || user?.username || "there").split(" ")[0];

  const lifeScoreTrend = useMemo(() => {
    const ordered = [...lifeScoreHistory].sort((a, b) => toDate(a.computed_at).getTime() - toDate(b.computed_at).getTime());
    const latest = ordered[ordered.length - 1]?.score ?? score;
    const previous = ordered[ordered.length - 2]?.score ?? latest;
    return {
      delta: Number((latest - previous).toFixed(1)),
      chart: ordered.slice(-21).map((point) => ({
        day: format(toDate(point.computed_at), "MMM d"),
        score: Number(point.score),
      })),
    };
  }, [lifeScoreHistory, score]);

  const sleepTrend = useMemo(() => {
    return timeline
      .filter((event) => event.type === "sleep")
      .map((event) => ({ day: format(toDate(event.date), "MMM d"), hours: Number(event.value) }))
      .sort((a, b) => (a.day > b.day ? 1 : -1))
      .slice(-14);
  }, [timeline]);

  const energyCurve = useMemo(() => {
    const hourly = energyForecast?.hourly_scores || {};
    return Object.entries(hourly)
      .map(([hour, value]) => ({ hour, score: Number(value) }))
      .sort((a, b) => a.hour.localeCompare(b.hour));
  }, [energyForecast]);

  const habitHeatmap = useMemo(() => {
    const completionMap = new Map<string, number>();
    for (const event of timeline) {
      if (event.type === "habits") {
        completionMap.set(event.date, Number(event.value));
      }
    }

    return Array.from({ length: 28 }).map((_, index) => {
      const day = addDays(new Date(), -(27 - index));
      const key = format(day, "yyyy-MM-dd");
      const value = completionMap.get(key) ?? 0;
      return {
        key,
        label: format(day, "MMM d"),
        value,
      };
    });
  }, [timeline]);

  const calendarRows = useMemo(() => {
    if (calendarEvents.length > 0) {
      return calendarEvents.slice(0, 6).map((event) => ({
        id: event.id,
        title: event.title,
        time: `${format(new Date(event.start), "HH:mm")} - ${format(new Date(event.end), "HH:mm")}`,
        source: event.source,
      }));
    }

    return (plan?.blocks || []).slice(0, 6).map((block) => ({
      id: block.id,
      title: block.title,
      time: `${block.start_time.slice(0, 5)} - ${block.end_time.slice(0, 5)}`,
      source: block.category,
    }));
  }, [calendarEvents, plan?.blocks]);

  const activeHabits = habits.filter((habit) => habit.is_active !== false).length;
  const maxStreak = habits.reduce((max, habit) => Math.max(max, Number(habit.current_streak || 0)), 0);

  const visibleWarnings = warningsExpanded ? warnings : warnings.slice(0, 3);

  const resolveWarning = async (warningId: string) => {
    try {
      await api.intelligence.resolveWarning(warningId);
      setWarnings((prev) => prev.filter((warning) => warning.id !== warningId));
    } catch {
      setError("Failed to resolve warning.");
    }
  };

  return (
    <div className="space-y-6">
      {error ? <InsightBanner text={error} type="danger" /> : null}

      {calendarConflicts.length > 0 ? (
        <InsightBanner
          text={`${calendarConflicts.length} calendar conflict(s) detected between William blocks and Google events.`}
          type="warning"
        />
      ) : null}

      <section className="grid gap-4 xl:grid-cols-3">
        <AppCard className="xl:col-span-2">
          <div className="flex items-center justify-between">
            <p className="section-label inline-flex items-center gap-2">
              <AlertTriangle className="h-4 w-4 text-warning" /> Predictive Warnings
            </p>
            <button
              type="button"
              onClick={() => setWarningsExpanded((prev) => !prev)}
              className="rounded-lg border border-border px-3 py-1.5 text-xs text-text-secondary"
            >
              {warningsExpanded ? "Collapse" : "Expand"}
            </button>
          </div>
          <div className="mt-3 space-y-2">
            {visibleWarnings.length === 0 ? (
              <p className="text-sm text-text-secondary">No active warnings right now.</p>
            ) : (
              visibleWarnings.map((warning) => (
                <div key={warning.id} className="rounded-lg border border-border bg-surface-raised p-3">
                  <div className="flex items-start justify-between gap-2">
                    <div>
                      <p className="text-sm font-semibold text-text-primary">{warning.warning_type.replaceAll("_", " ")}</p>
                      <p className="text-xs text-text-secondary">Severity: {warning.severity}</p>
                    </div>
                    <button
                      type="button"
                      onClick={() => void resolveWarning(warning.id)}
                      className="rounded-lg border border-border px-2 py-1 text-xs"
                    >
                      Resolve
                    </button>
                  </div>
                  <p className="mt-2 text-sm text-text-primary">{warning.explanation}</p>
                  <p className="mt-1 text-xs text-text-secondary">Action: {warning.recommended_action}</p>
                </div>
              ))
            )}
          </div>
        </AppCard>

        <AppCard>
          <p className="section-label">Burnout Risk</p>
          <div className="mt-3 space-y-2">
            <p className="text-3xl font-semibold text-text-primary">{Number(burnoutScore?.score ?? 0).toFixed(0)}</p>
            <p className="text-sm capitalize text-text-secondary">{String(burnoutScore?.severity ?? "unknown")}</p>
            <p className="text-xs text-text-secondary">{String(burnoutScore?.recommendation ?? "No recommendation yet")}</p>
            <button
              type="button"
              onClick={() =>
                void api.intelligence.interveneBurnout().then(() => {
                  void api.intelligence.burnoutScore().then((payload) => {
                    setBurnoutScore(payload);
                  });
                })
              }
              className="mt-2 rounded-lg bg-accent px-3 py-2 text-xs font-semibold text-white"
            >
              Trigger Intervention
            </button>
          </div>
        </AppCard>
      </section>

      <motion.section variants={staggerContainer} initial="initial" animate="animate" className="grid gap-4 xl:grid-cols-3">
        <motion.div variants={fadeMotion} className="xl:col-span-2">
          <AppCard className="h-full bg-gradient-to-br from-surface to-surface-raised">
            <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
              <div>
                <p className="section-label">Daily Command Center</p>
                <h2 className="page-title mt-2">Good morning, {todayName}</h2>
                <p className="body-copy mt-2 max-w-2xl">
                  Your life score is {score}. Track the trend, stabilize sleep consistency, and defend your focus blocks.
                </p>
              </div>
              <ProgressRing
                value={score}
                size="lg"
                label="Life Score"
                sublabel={lifeScore?.explanation || "Log across modules to strengthen signal quality."}
              />
            </div>

            <div className="mt-6 grid gap-3 md:grid-cols-3">
              <div className="rounded-lg border border-border bg-surface p-3">
                <p className="meta-copy">24h Change</p>
                <p className={`mt-1 text-lg font-semibold ${lifeScoreTrend.delta >= 0 ? "text-success" : "text-danger"}`}>
                  {lifeScoreTrend.delta >= 0 ? "+" : ""}
                  {lifeScoreTrend.delta}
                </p>
              </div>
              <div className="rounded-lg border border-border bg-surface p-3">
                <p className="meta-copy">Active Habits</p>
                <p className="mt-1 text-lg font-semibold text-text-primary">{activeHabits}</p>
              </div>
              <div className="rounded-lg border border-border bg-surface p-3">
                <p className="meta-copy">Longest Streak</p>
                <p className="mt-1 text-lg font-semibold text-text-primary">{maxStreak}d</p>
              </div>
            </div>

            <div className="mt-4 h-44">
              {loading ? (
                <SkeletonLoader variant="card" />
              ) : (
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={lifeScoreTrend.chart}>
                    <CartesianGrid strokeDasharray="3 3" stroke="rgba(148,163,184,0.15)" />
                    <XAxis dataKey="day" tick={{ fill: "rgb(var(--color-text-muted))", fontSize: 11 }} />
                    <YAxis domain={[0, 100]} tick={{ fill: "rgb(var(--color-text-muted))", fontSize: 11 }} />
                    <Tooltip />
                    <Line dataKey="score" type="monotone" stroke="rgb(var(--color-accent))" strokeWidth={2.6} dot={false} />
                  </LineChart>
                </ResponsiveContainer>
              )}
            </div>
          </AppCard>
        </motion.div>

        <motion.div variants={fadeMotion}>
          <AppCard className="h-full">
            <div className="flex items-center justify-between">
              <p className="section-label">Weekly Review</p>
              {weeklyReview ? <Badge label={weeklyReview.trend} variant={mapTrendVariant(weeklyReview.trend)} /> : null}
            </div>
            {loading ? (
              <div className="mt-4 space-y-3">
                <SkeletonLoader variant="text" lines={5} />
              </div>
            ) : (
              <div className="mt-4 space-y-3">
                <div className="rounded-lg border border-border bg-surface-raised p-3">
                  <p className="meta-copy">Average Score</p>
                  <p className="mt-1 text-lg font-semibold text-text-primary">{weeklyReview?.avg_score?.toFixed(1) || "--"}</p>
                </div>
                <div className="rounded-lg border border-border bg-surface-raised p-3">
                  <p className="meta-copy">Best Day</p>
                  <p className="mt-1 text-sm font-semibold text-success">{weeklyReview?.best_day || "No data"}</p>
                </div>
                <div className="rounded-lg border border-border bg-surface-raised p-3">
                  <p className="meta-copy">Worst Day</p>
                  <p className="mt-1 text-sm font-semibold text-danger">{weeklyReview?.worst_day || "No data"}</p>
                </div>
                <p className="rounded-lg border border-accent/25 bg-accent/10 p-3 text-sm text-text-primary">
                  {weeklyReview?.william_summary || "Weekly review will appear as soon as score history is available."}
                </p>
              </div>
            )}
          </AppCard>
        </motion.div>
      </motion.section>

      <motion.section variants={staggerContainer} initial="initial" animate="animate" className="grid gap-4 xl:grid-cols-3">
        <motion.div variants={fadeMotion}>
          <AppCard className="h-full">
            <p className="section-label">Sleep Trend</p>
            <div className="mt-4 h-56">
              {loading ? (
                <SkeletonLoader variant="card" />
              ) : (
                <ResponsiveContainer width="100%" height="100%">
                  <AreaChart data={sleepTrend}>
                    <defs>
                      <linearGradient id="sleepFill" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor="rgb(var(--color-info))" stopOpacity={0.4} />
                        <stop offset="95%" stopColor="rgb(var(--color-info))" stopOpacity={0.02} />
                      </linearGradient>
                    </defs>
                    <CartesianGrid strokeDasharray="3 3" stroke="rgba(148,163,184,0.15)" />
                    <XAxis dataKey="day" tick={{ fill: "rgb(var(--color-text-muted))", fontSize: 11 }} />
                    <YAxis tick={{ fill: "rgb(var(--color-text-muted))", fontSize: 11 }} />
                    <Tooltip />
                    <Area type="monotone" dataKey="hours" stroke="rgb(var(--color-info))" fill="url(#sleepFill)" strokeWidth={2.2} />
                  </AreaChart>
                </ResponsiveContainer>
              )}
            </div>
          </AppCard>
        </motion.div>

        <motion.div variants={fadeMotion}>
          <AppCard className="h-full">
            <p className="section-label">Habit Heatmap</p>
            <div className="mt-4 grid grid-cols-7 gap-2">
              {loading
                ? Array.from({ length: 28 }).map((_, index) => <SkeletonLoader key={index} variant="circle" />)
                : habitHeatmap.map((cell) => {
                    const opacity = Math.min(0.95, Math.max(0.08, cell.value / 100));
                    return (
                      <div key={cell.key} className="flex flex-col items-center gap-1">
                        <div
                          title={`${cell.label}: ${cell.value.toFixed(0)}% completion`}
                          className="h-8 w-8 rounded-md border border-border"
                          style={{
                            backgroundColor: `rgba(16, 185, 129, ${opacity})`,
                          }}
                        />
                        <span className="text-[10px] text-text-muted">{format(toDate(cell.key), "d")}</span>
                      </div>
                    );
                  })}
            </div>
            <p className="meta-copy mt-3">Last 28 days of completed habit ratio.</p>
          </AppCard>
        </motion.div>

        <motion.div variants={fadeMotion}>
          <AppCard className="h-full">
            <p className="section-label">Energy Curve</p>
            <div className="mt-4 h-56">
              {loading ? (
                <SkeletonLoader variant="card" />
              ) : (
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={energyCurve}>
                    <CartesianGrid strokeDasharray="3 3" stroke="rgba(148,163,184,0.15)" />
                    <XAxis dataKey="hour" tick={{ fill: "rgb(var(--color-text-muted))", fontSize: 11 }} />
                    <YAxis tick={{ fill: "rgb(var(--color-text-muted))", fontSize: 11 }} domain={[0, 10]} />
                    <Tooltip />
                    <Bar dataKey="score" fill="rgb(var(--color-warning))" radius={[4, 4, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              )}
            </div>
          </AppCard>
        </motion.div>
      </motion.section>

      <motion.section variants={staggerContainer} initial="initial" animate="animate" className="grid gap-4 xl:grid-cols-3">
        <motion.div variants={fadeMotion} className="xl:col-span-2">
          <AppCard className="h-full">
            <div className="flex items-center justify-between">
              <p className="section-label">Calendar Today</p>
              <button
                type="button"
                onClick={() => navigate("/timeline")}
                className="rounded-lg border border-border px-3 py-1.5 text-xs text-text-secondary transition hover:text-text-primary"
              >
                Open Timeline
              </button>
            </div>
            <div className="mt-4 space-y-2">
              {loading ? (
                <SkeletonLoader variant="text" lines={8} />
              ) : calendarRows.length === 0 ? (
                <p className="body-copy">No calendar or schedule items for today.</p>
              ) : (
                calendarRows.map((item) => (
                  <div key={item.id} className="flex items-center justify-between rounded-lg border border-border bg-surface-raised p-3">
                    <div className="min-w-0">
                      <p className="truncate text-sm font-medium text-text-primary">{item.title}</p>
                      <p className="meta-copy mt-1">{item.source}</p>
                    </div>
                    <div className="inline-flex items-center gap-1 text-xs text-text-secondary">
                      <Clock3 className="h-3.5 w-3.5" /> {item.time}
                    </div>
                  </div>
                ))
              )}
            </div>
          </AppCard>
        </motion.div>

        <motion.div variants={fadeMotion}>
          <AppCard className="h-full">
            <p className="section-label">Quick Actions</p>
            <div className="mt-4 grid gap-2">
              <QuickActionButton icon={<Target className="h-4 w-4" />} label="Habits" onClick={() => navigate("/habits")} />
              <QuickActionButton icon={<Moon className="h-4 w-4" />} label="Sleep" onClick={() => navigate("/sleep")} />
              <QuickActionButton icon={<HeartPulse className="h-4 w-4" />} label="Fitness" onClick={() => navigate("/fitness")} />
              <QuickActionButton icon={<CalendarDays className="h-4 w-4" />} label="Timeline" onClick={() => navigate("/timeline")} />
            </div>
          </AppCard>
        </motion.div>
      </motion.section>

      <motion.section variants={staggerContainer} initial="initial" animate="animate" className="grid gap-4 xl:grid-cols-3">
        <motion.div variants={fadeMotion}>
          <AppCard className="h-full">
            <p className="section-label">Life Score Components</p>
            <div className="mt-4 space-y-2">
              {Object.entries(lifeScore?.component_scores || {}).map(([key, value]) => (
                <div key={key}>
                  <div className="mb-1 flex items-center justify-between text-xs text-text-secondary">
                    <span className="capitalize">{key}</span>
                    <span>{Math.round(Number(value))}</span>
                  </div>
                  <div className="h-2 rounded-full bg-surface-raised">
                    <div
                      className="h-2 rounded-full bg-accent"
                      style={{ width: `${Math.min(100, Math.max(0, Number(value)))}%` }}
                    />
                  </div>
                </div>
              ))}
            </div>
          </AppCard>
        </motion.div>

        <motion.div variants={fadeMotion}>
          <AppCard className="h-full">
            <p className="section-label">Momentum Signals</p>
            <div className="mt-4 space-y-3">
              <div className="rounded-lg border border-border bg-surface-raised p-3">
                <p className="inline-flex items-center gap-2 text-sm text-text-primary">
                  <Flame className="h-4 w-4 text-warning" /> Habit streak stability
                </p>
                <p className="meta-copy mt-1">Strong streaks protect your score in low-energy windows.</p>
              </div>
              <div className="rounded-lg border border-border bg-surface-raised p-3">
                <p className="inline-flex items-center gap-2 text-sm text-text-primary">
                  <Zap className="h-4 w-4 text-info" /> Energy pacing
                </p>
                <p className="meta-copy mt-1">Place deep work in your top 3 energy hours to reduce score volatility.</p>
              </div>
              <div className="rounded-lg border border-border bg-surface-raised p-3">
                <p className="inline-flex items-center gap-2 text-sm text-text-primary">
                  <Activity className="h-4 w-4 text-accent" /> Recovery rhythm
                </p>
                <p className="meta-copy mt-1">Sleep consistency currently has the highest cross-module impact.</p>
              </div>
            </div>
          </AppCard>
        </motion.div>

        <motion.div variants={fadeMotion}>
          <AppCard className="h-full border-accent/30 bg-gradient-to-br from-surface to-surface-raised">
            <p className="section-label inline-flex items-center gap-2">
              <Sparkles className="h-4 w-4" /> William Note
            </p>
            <p className="mt-4 text-sm text-text-primary">
              "Keep your bedtime variance tight for the next 7 days. That single constraint can unlock cleaner habit completion and a higher weekly average score."
            </p>
            <button
              type="button"
              onClick={() => navigate("/chat", { state: { prefill: "Give me a 7-day recovery strategy based on my dashboard" } })}
              className="mt-5 inline-flex items-center gap-2 rounded-lg bg-accent px-4 py-2 text-sm font-semibold text-white transition hover:bg-accent-hover"
            >
              <LineChart className="h-4 w-4" /> Plan With William
            </button>
          </AppCard>
        </motion.div>
      </motion.section>
    </div>
  );
}
