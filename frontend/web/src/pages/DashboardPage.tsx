import { format } from "date-fns";
import {
  AlarmClock,
  AlertTriangle,
  CalendarClock,
  CheckCircle2,
  Flame,
  HeartPulse,
  Sparkles,
  Stethoscope,
  WandSparkles,
  X,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import ActivityFeed from "../components/ActivityFeed";
import AgentsPanel from "../components/AgentsPanel";
import Modal from "../components/Modal";
import LifeScoreCard from "../components/LifeScoreCard";
import MorningBriefingCard from "../components/MorningBriefingCard";
import GamificationPanel from "../components/GamificationPanel";
import StatCard from "../components/StatCard";
import TimelineBlock from "../components/TimelineBlock";
import { useCountdown } from "../hooks/useCountdown";
import { api } from "../services/api";
import {
  ActivityFeedItem,
  AgentRecommendationLog,
  AgentStatus,
  DailyPlan,
  GamificationProfile,
  Habit,
  LifeScore,
  LifeScoreHistoryPoint,
  MedicineReminder,
  MorningBriefing,
  PredictiveWarning,
} from "../types/api";

function toReminderDate(reminder?: MedicineReminder) {
  if (!reminder) {
    return null;
  }
  const today = new Date();
  const [h, m] = reminder.scheduled_time.slice(0, 5).split(":").map(Number);
  const dt = new Date(today);
  dt.setHours(h, m, 0, 0);
  if (dt.getTime() < today.getTime()) {
    dt.setDate(dt.getDate() + 1);
  }
  return dt;
}

export default function DashboardPage() {
  const [plan, setPlan] = useState<DailyPlan | null>(null);
  const [habits, setHabits] = useState<Habit[]>([]);
  const [reminders, setReminders] = useState<MedicineReminder[]>([]);
  const [energyForecast, setEnergyForecast] = useState<Record<string, unknown> | null>(null);
  const [lifeScore, setLifeScore] = useState<LifeScore | null>(null);
  const [lifeScoreHistory, setLifeScoreHistory] = useState<LifeScoreHistoryPoint[]>([]);
  const [gamificationProfile, setGamificationProfile] = useState<GamificationProfile | null>(null);
  const [activityFeedItems, setActivityFeedItems] = useState<ActivityFeedItem[]>([]);
  const [activityFeedCursor, setActivityFeedCursor] = useState<string | null>(null);
  const [activityFeedHasMore, setActivityFeedHasMore] = useState(false);
  const [activityFeedLoadingMore, setActivityFeedLoadingMore] = useState(false);
  const [briefing, setBriefing] = useState<MorningBriefing | null>(null);
  const [briefingSending, setBriefingSending] = useState(false);
  const [warnings, setWarnings] = useState<PredictiveWarning[]>([]);
  const [dismissedWarningIds, setDismissedWarningIds] = useState<string[]>([]);
  const [agentStatuses, setAgentStatuses] = useState<AgentStatus[]>([]);
  const [agentRecommendations, setAgentRecommendations] = useState<AgentRecommendationLog[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [rescheduleOpen, setRescheduleOpen] = useState(false);
  const [rescheduleReason, setRescheduleReason] = useState("Need to optimize for deep work and calls");

  const load = async () => {
    setLoading(true);
    setError("");
    try {
      const [
        todayPlan,
        habitList,
        upcoming,
        energy,
        score,
        scoreHistory,
        todayBriefing,
        profile,
        feedPage,
        warningRows,
        statuses,
        recommendations,
      ] = await Promise.all([
        api.scheduler.today().catch(() => null),
        api.habits.list({ active_only: true, limit: 100, offset: 0 }),
        api.medicine.upcoming(180).catch(() => []),
        api.fitness.energyByDate(format(new Date(), "yyyy-MM-dd")).catch(() => null),
        api.intelligence.lifeScore().catch(() => null),
        api.intelligence.lifeScoreHistory(30).catch(() => []),
        api.briefing.today().catch(() => null),
        api.gamification.profile().catch(() => null),
        api.feed.list({ limit: 20 }).catch(() => null),
        api.intelligence.warnings().catch(() => []),
        api.agents.status().catch(() => []),
        api.agents.recommendations({ limit: 12 }).catch(() => []),
      ]);
      setPlan(todayPlan);
      setHabits(habitList);
      setReminders(upcoming);
      setEnergyForecast(energy);
      setLifeScore(score);
      setLifeScoreHistory(scoreHistory);
      setBriefing(todayBriefing);
      setGamificationProfile(profile);
      setActivityFeedItems(feedPage?.items ?? []);
      setActivityFeedCursor(feedPage?.next_cursor ?? null);
      setActivityFeedHasMore(Boolean(feedPage?.has_more));
      setWarnings(warningRows ?? []);
      setAgentStatuses(statuses ?? []);
      setAgentRecommendations(recommendations ?? []);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to load dashboard");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void load();
  }, []);

  const completedBlocks = useMemo(
    () => plan?.blocks.filter((block) => block.status === "completed").length ?? 0,
    [plan],
  );

  const checkedHabits = useMemo(
    () => habits.filter((habit) => (habit.current_streak ?? 0) > 0).length,
    [habits],
  );

  const maxStreak = useMemo(
    () => habits.reduce((max, habit) => Math.max(max, habit.current_streak ?? 0), 0),
    [habits],
  );

  const nextReminder = reminders[0];
  const countdown = useCountdown(toReminderDate(nextReminder));

  const onGenerateSchedule = async () => {
    await api.scheduler.generate(format(new Date(), "yyyy-MM-dd"), {});
    await load();
  };

  const onStartBlock = async (blockId: string) => {
    await api.scheduler.startBlock(blockId);
    await load();
  };

  const onCompleteBlock = async (blockId: string) => {
    await api.scheduler.updateBlock(blockId, { status: "completed" });
    await load();
  };

  const onReschedule = async () => {
    await api.scheduler.reschedule(format(new Date(), "yyyy-MM-dd"), {
      reason: rescheduleReason,
      trigger: "manual",
    });
    setRescheduleOpen(false);
    await load();
  };

  const onSendBriefingNow = async () => {
    setBriefingSending(true);
    try {
      const sent = await api.briefing.sendNow();
      setBriefing(sent.briefing);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to send morning briefing");
    } finally {
      setBriefingSending(false);
    }
  };

  const onLoadMoreFeed = async () => {
    if (activityFeedLoadingMore || !activityFeedHasMore || !activityFeedCursor) {
      return;
    }

    setActivityFeedLoadingMore(true);
    try {
      const nextPage = await api.feed.list({
        limit: 20,
        before_cursor: activityFeedCursor,
      });

      setActivityFeedItems((previous) => {
        const seen = new Set(previous.map((item) => item.event_id));
        const incoming = nextPage.items.filter((item) => !seen.has(item.event_id));
        return [...previous, ...incoming];
      });
      setActivityFeedCursor(nextPage.next_cursor ?? null);
      setActivityFeedHasMore(Boolean(nextPage.has_more));
    } catch {
      setActivityFeedHasMore(false);
    } finally {
      setActivityFeedLoadingMore(false);
    }
  };

  const visibleWarnings = warnings.filter((item) => !dismissedWarningIds.includes(item.id));

  const warningTone = (severity: string) => {
    if (severity === "critical") {
      return "border-[rgb(var(--danger))] bg-red-500/10";
    }
    if (severity === "high") {
      return "border-[rgb(var(--warning))] bg-orange-500/10";
    }
    if (severity === "medium") {
      return "border-yellow-500/50 bg-yellow-500/10";
    }
    return "border-[rgb(var(--border))] bg-[rgb(var(--bg-muted))]";
  };

  return (
    <div className="grid gap-6 xl:grid-cols-5">
      <section className="xl:col-span-5">
        <MorningBriefingCard
          briefing={briefing}
          loading={loading}
          sending={briefingSending}
          onSendNow={onSendBriefingNow}
        />
      </section>

      {visibleWarnings.length > 0 ? (
        <section className="xl:col-span-5 space-y-2">
          {visibleWarnings.map((warning) => (
            <article key={warning.id} className={`rounded-xl border p-3 ${warningTone(warning.severity)}`}>
              <div className="flex items-start justify-between gap-3">
                <div>
                  <p className="text-xs font-semibold uppercase tracking-wide">{warning.warning_type.replace(/_/g, " ")}</p>
                  <p className="mt-1 text-sm">
                    <AlertTriangle className="mr-1 inline h-4 w-4" />
                    {warning.explanation}
                  </p>
                  <p className="mt-1 text-xs text-[rgb(var(--text-dim))]">Recommended: {warning.recommended_action}</p>
                </div>
                <button
                  type="button"
                  className="rounded-lg border border-[rgb(var(--border))] p-1"
                  onClick={() => setDismissedWarningIds((previous) => [...previous, warning.id])}
                >
                  <X className="h-4 w-4" />
                </button>
              </div>
            </article>
          ))}
        </section>
      ) : null}

      <section className="xl:col-span-3">
        <div className="mb-4 flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold">Today’s schedule</h1>
            <p className="text-sm text-[rgb(var(--text-dim))]">{format(new Date(), "EEEE, MMMM do")}</p>
          </div>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => setRescheduleOpen(true)}
              className="rounded-xl border border-[rgb(var(--border))] bg-[rgb(var(--bg-elevated))] px-3 py-2 text-sm font-medium"
            >
              Reschedule
            </button>
            {!plan ? (
              <button
                type="button"
                onClick={() => void onGenerateSchedule()}
                className="inline-flex items-center gap-2 rounded-xl bg-[rgb(var(--primary))] px-3 py-2 text-sm font-semibold text-white"
              >
                <WandSparkles className="h-4 w-4" /> Generate schedule
              </button>
            ) : null}
          </div>
        </div>

        {loading ? (
          <div className="card p-8 text-sm text-[rgb(var(--text-dim))]">Loading timeline...</div>
        ) : error ? (
          <div className="card p-6 text-sm text-[rgb(var(--danger))]">{error}</div>
        ) : plan?.blocks?.length ? (
          <div className="space-y-3">
            {plan.blocks.map((block) => (
              <TimelineBlock key={block.id} block={block} onStart={onStartBlock} onComplete={onCompleteBlock} />
            ))}
          </div>
        ) : (
          <div className="card p-8 text-center">
            <CalendarClock className="mx-auto h-8 w-8 text-[rgb(var(--text-dim))]" />
            <p className="mt-2 text-sm text-[rgb(var(--text-dim))]">No schedule for today yet.</p>
          </div>
        )}
      </section>

      <aside className="space-y-4 xl:col-span-2">
        <GamificationPanel profile={gamificationProfile} loading={loading} />

        <LifeScoreCard lifeScore={lifeScore} history={lifeScoreHistory} loading={loading} />

        <AgentsPanel statuses={agentStatuses} recommendations={agentRecommendations} loading={loading} />

        <ActivityFeed
          items={activityFeedItems}
          loading={loading}
          loadingMore={activityFeedLoadingMore}
          hasMore={activityFeedHasMore}
          onLoadMore={onLoadMoreFeed}
        />

        <div className="grid grid-cols-2 gap-3">
          <StatCard
            icon={CheckCircle2}
            label="Habits Done"
            value={`${checkedHabits}/${Math.max(habits.length, 1)}`}
            trend="today"
            tone="success"
          />
          <StatCard
            icon={AlarmClock}
            label="Medicine Due"
            value={nextReminder ? nextReminder.scheduled_time : "None"}
            trend={nextReminder ? `T-${countdown}` : "all clear"}
            tone="warning"
          />
          <StatCard icon={Flame} label="Best Active Streak" value={`${maxStreak} days`} trend="habits" tone="warning" />
          <StatCard
            icon={HeartPulse}
            label="Energy"
            value={
              energyForecast && typeof energyForecast === "object" && "peak_hours" in energyForecast
                ? (energyForecast.peak_hours as string[]).slice(0, 1).join(", ") || "N/A"
                : "N/A"
            }
            trend="peak window"
            tone="primary"
          />
        </div>

        <section className="card p-4">
          <h3 className="text-sm font-semibold">Upcoming reminders</h3>
          <div className="mt-3 space-y-2">
            {reminders.slice(0, 3).map((item) => (
              <div key={`${item.medicine_name}-${item.scheduled_time}`} className="rounded-xl bg-[rgb(var(--bg-muted))] p-2">
                <p className="text-sm font-medium">{item.medicine_name}</p>
                <p className="text-xs text-[rgb(var(--text-dim))]">
                  {item.dosage} at {item.scheduled_time}
                </p>
              </div>
            ))}
            {reminders.length === 0 ? (
              <p className="text-xs text-[rgb(var(--text-dim))]">No upcoming reminders.</p>
            ) : null}
          </div>
        </section>

        <section className="card p-4">
          <h3 className="text-sm font-semibold">Quick actions</h3>
          <div className="mt-3 grid grid-cols-2 gap-2">
            <button className="rounded-xl bg-[rgb(var(--bg-muted))] px-3 py-2 text-sm">Check In Habit</button>
            <button className="rounded-xl bg-[rgb(var(--bg-muted))] px-3 py-2 text-sm">Log Medicine</button>
            <button className="rounded-xl bg-[rgb(var(--bg-muted))] px-3 py-2 text-sm">New Journal Entry</button>
            <button className="rounded-xl bg-[rgb(var(--bg-muted))] px-3 py-2 text-sm">Voice Command</button>
          </div>
        </section>

        <section className="card p-4">
          <h3 className="mb-2 text-sm font-semibold">Live status</h3>
          <p className="text-sm text-[rgb(var(--text-dim))]">
            <Sparkles className="mr-1 inline h-4 w-4 text-[rgb(var(--primary))]" />
            Mission control synchronized with scheduler, habits, medicine, and fitness modules.
          </p>
          <p className="mt-2 text-xs text-[rgb(var(--text-dim))]">
            <Stethoscope className="mr-1 inline h-4 w-4" /> {completedBlocks} schedule blocks completed today.
          </p>
        </section>
      </aside>

      <Modal
        open={rescheduleOpen}
        title="AI Reschedule"
        onClose={() => setRescheduleOpen(false)}
        footer={
          <div className="flex justify-end gap-2">
            <button
              type="button"
              className="rounded-lg border border-[rgb(var(--border))] px-3 py-2 text-sm"
              onClick={() => setRescheduleOpen(false)}
            >
              Cancel
            </button>
            <button
              type="button"
              className="rounded-lg bg-[rgb(var(--primary))] px-3 py-2 text-sm font-semibold text-white"
              onClick={() => void onReschedule()}
            >
              Reschedule now
            </button>
          </div>
        }
      >
        <label className="block space-y-2">
          <span className="text-sm font-medium">What should change?</span>
          <textarea
            value={rescheduleReason}
            onChange={(event) => setRescheduleReason(event.target.value)}
            className="h-24 w-full rounded-xl border border-[rgb(var(--border))] bg-[rgb(var(--bg-muted))] p-3 text-sm"
          />
        </label>
      </Modal>
    </div>
  );
}
