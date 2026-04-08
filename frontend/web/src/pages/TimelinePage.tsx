import { endOfWeek, format, parseISO, startOfWeek } from "date-fns";
import { motion, useReducedMotion } from "framer-motion";
import { CalendarRange, Filter, MessageCircleQuestion, Sparkles, TrendingUp } from "lucide-react";
import { FormEvent, useEffect, useMemo, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { AppCard, Badge, InsightBanner, SkeletonLoader } from "../components/ui";
import { fadeInUp, reduceMotion, staggerContainer } from "../lib/animations";
import { api } from "../services/api";
import { LifeScoreHistoryPoint, TimelineEvent, WeeklyReview } from "../types/api";

const DAY_FILTERS = [30, 60, 90, 180];

const EVENT_COLORS: Record<string, string> = {
  life_score: "accent",
  sleep: "info",
  habits: "success",
  mood: "warning",
  workout: "success",
  study: "info",
  trade: "danger",
  decision: "accent",
};

function formatEventType(value: string) {
  return value.replace(/_/g, " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function safeDate(input: string) {
  if (input.includes("T")) {
    return parseISO(input);
  }
  return new Date(`${input}T00:00:00`);
}

export default function TimelinePage() {
  const [days, setDays] = useState(90);
  const [typeFilter, setTypeFilter] = useState("all");
  const [events, setEvents] = useState<TimelineEvent[]>([]);
  const [lifeHistory, setLifeHistory] = useState<LifeScoreHistoryPoint[]>([]);
  const [weeklySummary, setWeeklySummary] = useState("");
  const [askQuestion, setAskQuestion] = useState("");
  const [askAnswer, setAskAnswer] = useState("");
  const [askDates, setAskDates] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [asking, setAsking] = useState(false);
  const [error, setError] = useState("");

  const shouldReduceMotion = useReducedMotion();
  const fadeMotion = reduceMotion(shouldReduceMotion, fadeInUp);

  const load = async (windowDays: number) => {
    setLoading(true);
    setError("");
    try {
      const timelineRows = (await api.intelligence.timeline(windowDays)) as TimelineEvent[];
      const scoreHistory =
        (await api.intelligence.lifeScoreHistory(Math.max(120, windowDays)).catch(
          () => [] as LifeScoreHistoryPoint[],
        )) as LifeScoreHistoryPoint[];
      const review =
        (await api.briefing.weeklyReview().catch(() => null as WeeklyReview | null)) as
          WeeklyReview | null;
      setEvents(timelineRows);
      setLifeHistory(scoreHistory);
      setWeeklySummary(review?.william_summary || "");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to load timeline.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void load(days);
  }, [days]);

  const eventTypes = useMemo(() => {
    const unique = Array.from(new Set(events.map((item) => item.type))).sort();
    return ["all", ...unique];
  }, [events]);

  const filteredEvents = useMemo(() => {
    if (typeFilter === "all") {
      return events;
    }
    return events.filter((item) => item.type === typeFilter);
  }, [events, typeFilter]);

  const groupedEvents = useMemo(() => {
    const grouped = new Map<string, TimelineEvent[]>();
    for (const event of filteredEvents) {
      const key = event.date;
      const bucket = grouped.get(key) ?? [];
      bucket.push(event);
      grouped.set(key, bucket);
    }
    return Array.from(grouped.entries()).sort(([a], [b]) => (a < b ? 1 : -1));
  }, [filteredEvents]);

  const lifeScoreSeries = useMemo(() => {
    return lifeHistory
      .map((point) => ({
        date: format(safeDate(point.computed_at), "MMM d"),
        score: Math.round(Number(point.score || 0)),
      }))
      .slice(-42);
  }, [lifeHistory]);

  const weeklyWindow = useMemo(() => {
    const weekMap = new Map<string, { label: string; start: Date; scores: number[] }>();

    for (const point of lifeHistory) {
      const pointDate = safeDate(point.computed_at);
      const weekStart = startOfWeek(pointDate, { weekStartsOn: 1 });
      const key = format(weekStart, "yyyy-MM-dd");
      if (!weekMap.has(key)) {
        weekMap.set(key, {
          label: `${format(weekStart, "MMM d")} - ${format(endOfWeek(pointDate, { weekStartsOn: 1 }), "MMM d")}`,
          start: weekStart,
          scores: [],
        });
      }
      weekMap.get(key)?.scores.push(Number(point.score || 0));
    }

    const rows = Array.from(weekMap.values())
      .map((item) => ({
        label: item.label,
        avg: item.scores.length ? item.scores.reduce((sum, value) => sum + value, 0) / item.scores.length : 0,
        start: item.start,
      }))
      .sort((a, b) => a.start.getTime() - b.start.getTime());

    const best = rows.reduce((acc, row) => (row.avg > acc.avg ? row : acc), rows[0] ?? { label: "N/A", avg: 0, start: new Date() });
    const worst = rows.reduce((acc, row) => (row.avg < acc.avg ? row : acc), rows[0] ?? { label: "N/A", avg: 0, start: new Date() });

    return { rows, best, worst };
  }, [lifeHistory]);

  const correlationData = useMemo(() => {
    const aggregate = new Map<string, { sleep: number[]; habits: number[]; score: number[] }>();

    for (const event of events) {
      const key = event.date;
      if (!aggregate.has(key)) {
        aggregate.set(key, { sleep: [], habits: [], score: [] });
      }
      const row = aggregate.get(key);
      if (!row) {
        continue;
      }
      if (event.type === "sleep") {
        row.sleep.push(Number(event.value || 0));
      }
      if (event.type === "habits") {
        row.habits.push(Number(event.value || 0));
      }
      if (event.type === "life_score") {
        row.score.push(Number(event.value || 0));
      }
    }

    const toAvg = (values: number[]) => (values.length ? values.reduce((sum, value) => sum + value, 0) / values.length : null);

    const rows = Array.from(aggregate.entries())
      .map(([key, value]) => ({
        date: key,
        day: format(safeDate(key), "MMM d"),
        sleep: toAvg(value.sleep),
        habits: toAvg(value.habits),
        score: toAvg(value.score),
      }))
      .sort((a, b) => (a.date > b.date ? 1 : -1));

    return {
      sleepVsScore: rows.filter((row) => row.sleep !== null && row.score !== null).slice(-21),
      habitsVsScore: rows.filter((row) => row.habits !== null && row.score !== null).slice(-21),
    };
  }, [events]);

  const askTimeline = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const trimmed = askQuestion.trim();
    if (trimmed.length < 3) {
      return;
    }

    setAsking(true);
    try {
      const response = (await api.intelligence.askTimeline(trimmed)) as {
        answer: string;
        relevant_dates: string[];
      };
      setAskAnswer(response.answer);
      setAskDates(response.relevant_dates);
    } catch {
      setAskAnswer("I could not run timeline reasoning right now. Try again in a few seconds.");
      setAskDates([]);
    } finally {
      setAsking(false);
    }
  };

  return (
    <div className="space-y-6">
      {error ? <InsightBanner text={error} type="danger" /> : null}

      <AppCard className="bg-gradient-to-br from-surface to-surface-raised">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
          <div>
            <p className="section-label">Life Replay</p>
            <h2 className="page-title mt-2">Timeline Intelligence</h2>
            <p className="body-copy mt-2 max-w-2xl">
              Replay your recent months, ask William for causal patterns, and inspect what consistently moved your life score up or down.
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <label className="inline-flex items-center gap-2 rounded-lg border border-border bg-surface-raised px-3 py-2 text-xs text-text-secondary">
              <CalendarRange className="h-4 w-4" />
              <span>Window</span>
              <select
                value={days}
                onChange={(e) => setDays(Number(e.target.value))}
                className="bg-transparent text-text-primary outline-none"
              >
                {DAY_FILTERS.map((item) => (
                  <option key={item} value={item} className="bg-surface text-text-primary">
                    {item}d
                  </option>
                ))}
              </select>
            </label>

            <label className="inline-flex items-center gap-2 rounded-lg border border-border bg-surface-raised px-3 py-2 text-xs text-text-secondary">
              <Filter className="h-4 w-4" />
              <span>Type</span>
              <select
                value={typeFilter}
                onChange={(e) => setTypeFilter(e.target.value)}
                className="bg-transparent text-text-primary outline-none"
              >
                {eventTypes.map((item) => (
                  <option key={item} value={item} className="bg-surface text-text-primary">
                    {item === "all" ? "All" : formatEventType(item)}
                  </option>
                ))}
              </select>
            </label>
          </div>
        </div>
      </AppCard>

      <AppCard>
        <form onSubmit={askTimeline} className="flex flex-col gap-3 lg:flex-row lg:items-center">
          <div className="flex min-w-0 flex-1 items-center gap-2 rounded-lg border border-border bg-surface-raised px-3 py-2">
            <MessageCircleQuestion className="h-4 w-4 text-accent" />
            <input
              value={askQuestion}
              onChange={(e) => setAskQuestion(e.target.value)}
              placeholder="Ask timeline... e.g. What happened in my worst week?"
              className="w-full bg-transparent text-sm text-text-primary outline-none"
            />
          </div>
          <button
            type="submit"
            disabled={asking || askQuestion.trim().length < 3}
            className="rounded-lg bg-accent px-4 py-2 text-sm font-semibold text-white transition hover:bg-accent-hover disabled:cursor-not-allowed disabled:opacity-60"
          >
            {asking ? "Analyzing..." : "Ask William"}
          </button>
        </form>
        {askAnswer ? (
          <div className="mt-3 rounded-lg border border-border bg-surface-raised p-3">
            <p className="text-sm text-text-primary">{askAnswer}</p>
            {askDates.length > 0 ? (
              <div className="mt-2 flex flex-wrap gap-2">
                {askDates.map((item) => (
                  <Badge key={item} label={format(safeDate(item), "MMM d, yyyy")} variant="accent" />
                ))}
              </div>
            ) : null}
          </div>
        ) : null}
      </AppCard>

      <motion.section variants={staggerContainer} initial="initial" animate="animate" className="grid gap-4 lg:grid-cols-3">
        <motion.div variants={fadeMotion} className="lg:col-span-2">
          <AppCard className="h-full">
            <div className="flex items-center justify-between gap-3">
              <p className="section-label">Life Score Trend</p>
              <Badge label={`${lifeScoreSeries.length} points`} variant="default" />
            </div>
            <div className="mt-4 h-64">
              {loading ? (
                <SkeletonLoader variant="card" />
              ) : (
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={lifeScoreSeries}>
                    <CartesianGrid strokeDasharray="3 3" stroke="rgba(148,163,184,0.15)" />
                    <XAxis dataKey="date" tick={{ fill: "rgb(var(--color-text-muted))", fontSize: 11 }} />
                    <YAxis domain={[0, 100]} tick={{ fill: "rgb(var(--color-text-muted))", fontSize: 11 }} />
                    <Tooltip />
                    <Line type="monotone" dataKey="score" stroke="rgb(var(--color-accent))" strokeWidth={2.4} dot={false} />
                  </LineChart>
                </ResponsiveContainer>
              )}
            </div>
          </AppCard>
        </motion.div>

        <motion.div variants={fadeMotion}>
          <AppCard className="h-full">
            <p className="section-label">Best / Worst Week</p>
            <div className="mt-4 space-y-3">
              <div className="rounded-lg border border-border bg-surface-raised p-3">
                <p className="meta-copy">Best Week</p>
                <p className="mt-1 text-sm font-semibold text-text-primary">{weeklyWindow.best.label}</p>
                <p className="mt-1 text-sm text-success">Avg {weeklyWindow.best.avg.toFixed(1)}</p>
              </div>
              <div className="rounded-lg border border-border bg-surface-raised p-3">
                <p className="meta-copy">Worst Week</p>
                <p className="mt-1 text-sm font-semibold text-text-primary">{weeklyWindow.worst.label}</p>
                <p className="mt-1 text-sm text-danger">Avg {weeklyWindow.worst.avg.toFixed(1)}</p>
              </div>
              {weeklySummary ? (
                <div className="rounded-lg border border-accent/25 bg-accent/10 p-3 text-sm text-text-primary">
                  {weeklySummary}
                </div>
              ) : null}
            </div>
          </AppCard>
        </motion.div>
      </motion.section>

      <motion.section variants={staggerContainer} initial="initial" animate="animate" className="grid gap-4 lg:grid-cols-2">
        <motion.div variants={fadeMotion}>
          <AppCard className="h-full">
            <p className="section-label">Sleep vs Life Score</p>
            <div className="mt-4 h-56">
              {loading ? (
                <SkeletonLoader variant="card" />
              ) : (
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={correlationData.sleepVsScore}>
                    <CartesianGrid strokeDasharray="3 3" stroke="rgba(148,163,184,0.15)" />
                    <XAxis dataKey="day" tick={{ fill: "rgb(var(--color-text-muted))", fontSize: 11 }} />
                    <YAxis tick={{ fill: "rgb(var(--color-text-muted))", fontSize: 11 }} />
                    <Tooltip />
                    <Legend />
                    <Bar dataKey="sleep" name="Sleep Hours" fill="rgb(var(--color-info))" radius={[4, 4, 0, 0]} />
                    <Bar dataKey="score" name="Life Score" fill="rgb(var(--color-accent))" radius={[4, 4, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              )}
            </div>
          </AppCard>
        </motion.div>

        <motion.div variants={fadeMotion}>
          <AppCard className="h-full">
            <p className="section-label">Habits vs Life Score</p>
            <div className="mt-4 h-56">
              {loading ? (
                <SkeletonLoader variant="card" />
              ) : (
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={correlationData.habitsVsScore}>
                    <CartesianGrid strokeDasharray="3 3" stroke="rgba(148,163,184,0.15)" />
                    <XAxis dataKey="day" tick={{ fill: "rgb(var(--color-text-muted))", fontSize: 11 }} />
                    <YAxis tick={{ fill: "rgb(var(--color-text-muted))", fontSize: 11 }} />
                    <Tooltip />
                    <Legend />
                    <Bar dataKey="habits" name="Habit Completion %" fill="rgb(var(--color-success))" radius={[4, 4, 0, 0]} />
                    <Bar dataKey="score" name="Life Score" fill="rgb(var(--color-accent))" radius={[4, 4, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              )}
            </div>
          </AppCard>
        </motion.div>
      </motion.section>

      <motion.section variants={staggerContainer} initial="initial" animate="animate">
        <motion.div variants={fadeMotion}>
          <AppCard>
            <div className="flex items-center justify-between gap-3">
              <div>
                <p className="section-label">Grouped Timeline Feed</p>
                <p className="meta-copy mt-1">{filteredEvents.length} events in current filter</p>
              </div>
              <Badge label={typeFilter === "all" ? "All Modules" : formatEventType(typeFilter)} variant="accent" />
            </div>

            <div className="mt-4 max-h-[560px] space-y-4 overflow-y-auto pr-1">
              {loading ? (
                <SkeletonLoader variant="text" lines={10} />
              ) : groupedEvents.length === 0 ? (
                <p className="body-copy">No timeline events in this filter.</p>
              ) : (
                groupedEvents.map(([groupDate, rows]) => (
                  <div key={groupDate} className="rounded-lg border border-border bg-surface-raised p-3">
                    <div className="mb-3 flex items-center justify-between">
                      <p className="text-sm font-semibold text-text-primary">{format(safeDate(groupDate), "EEEE, MMM d")}</p>
                      <p className="meta-copy">{rows.length} events</p>
                    </div>
                    <div className="space-y-2">
                      {rows.map((item, idx) => (
                        <div key={`${groupDate}-${item.type}-${idx}`} className="flex flex-col gap-2 rounded-lg border border-border bg-surface px-3 py-2 md:flex-row md:items-center md:justify-between">
                          <div className="min-w-0">
                            <p className="text-sm text-text-primary">{item.label}</p>
                            <p className="meta-copy mt-1">{Object.keys(item.metadata || {}).length > 0 ? JSON.stringify(item.metadata) : "No metadata"}</p>
                          </div>
                          <div className="flex items-center gap-2">
                            <Badge
                              label={formatEventType(item.type)}
                              variant={(EVENT_COLORS[item.type] as "default" | "success" | "warning" | "danger" | "accent") || "default"}
                            />
                            <span className="text-xs font-semibold text-text-secondary">
                              {typeof item.value === "number" ? item.value.toFixed(1) : item.value}
                            </span>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                ))
              )}
            </div>
          </AppCard>
        </motion.div>
      </motion.section>

      <AppCard className="border-accent/20 bg-gradient-to-r from-surface to-surface-raised">
        <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
          <div>
            <p className="section-label flex items-center gap-2">
              <Sparkles className="h-4 w-4" /> Timeline Pattern Hint
            </p>
            <p className="mt-2 text-sm text-text-primary">
              Use the Ask bar above for prompts like "What caused my lowest score week?" or "Which days had strong sleep + habit completion overlap?"
            </p>
          </div>
          <div className="inline-flex items-center gap-2 rounded-lg bg-accent/15 px-3 py-2 text-sm text-accent">
            <TrendingUp className="h-4 w-4" /> Correlations update from live module events
          </div>
        </div>
      </AppCard>
    </div>
  );
}
