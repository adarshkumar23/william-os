import { format } from "date-fns";
import { motion, useReducedMotion } from "framer-motion";
import {
  Activity,
  BookOpen,
  Bot,
  Dumbbell,
  HeartPulse,
  Moon,
  NotebookPen,
  Pill,
  Sparkles,
  Target,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";

import { useAuth } from "../contexts/AuthContext";
import { fadeInUp, reduceMotion, staggerContainer } from "../lib/animations";
import { api } from "../services/api";
import {
  ActivityFeedItem,
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
import {
  AppCard,
  Badge,
  InsightBanner,
  ProgressRing,
  QuickActionButton,
  SkeletonLoader,
  StatCard,
  TimelineCard,
} from "../components/ui";

function numeric(value: unknown, fallback = 0) {
  if (typeof value === "number") {
    return value;
  }
  if (typeof value === "string") {
    const parsed = Number(value);
    if (!Number.isNaN(parsed)) {
      return parsed;
    }
  }
  return fallback;
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
  const [briefing, setBriefing] = useState<MorningBriefing | null>(null);
  const [warnings, setWarnings] = useState<PredictiveWarning[]>([]);
  const [agentStatuses, setAgentStatuses] = useState<AgentStatus[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [briefingOpen, setBriefingOpen] = useState(true);

  const navigate = useNavigate();
  const { user } = useAuth();
  const shouldReduceMotion = useReducedMotion();
  const fadeMotion = reduceMotion(shouldReduceMotion, fadeInUp);

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
        chatSessions,
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
        api.chat.listSessions().catch(() => []),
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
      setWarnings(warningRows ?? []);
      setAgentStatuses(chatSessions.filter(s => s.agent_name === 'os').slice(0, 1) as any);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to load dashboard");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void load();
  }, []);

  const score = Math.round(lifeScore?.score ?? 0);
  const lifeExplanation =
    lifeScore?.explanation || briefing?.ai_recommendation_of_day || "Complete your first module check-ins for a stronger score signal.";
  const todayName = String(user?.full_name || user?.username || "there").split(" ")[0];

  const scheduleRows = (plan?.blocks || []).slice(0, 6);
  const feedRows = activityFeedItems.slice(0, 10);

  const trendValue = useMemo(() => {
    if (lifeScoreHistory.length < 2) {
      return 0;
    }
    const latest = lifeScoreHistory[0]?.score ?? 0;
    const previous = lifeScoreHistory[1]?.score ?? 0;
    return latest - previous;
  }, [lifeScoreHistory]);

  const summaryStats = useMemo(() => {
    const habitStreak = habits.reduce((max, item) => Math.max(max, item.current_streak || 0), 0);
    const sleepScore = lifeScore?.component_scores?.sleep ?? 0;
    const studySessions = (plan?.blocks || []).filter((item) => item.category === "study").length;
    const xpWeek = numeric((gamificationProfile?.weekly_momentum as Record<string, unknown> | undefined)?.xp_earned_week, 0);

    return [
      {
        label: "Habit Streak",
        value: habitStreak,
        trend: 3.6,
        unit: "days",
        icon: <Target className="h-4 w-4" />,
      },
      {
        label: "Sleep Score",
        value: Math.round(sleepScore),
        trend: 1.2,
        icon: <Moon className="h-4 w-4" />,
      },
      {
        label: "Energy Level",
        value: numeric((energyForecast as Record<string, unknown> | null)?.score, 72),
        trend: 2.5,
        icon: <HeartPulse className="h-4 w-4" />,
      },
      {
        label: "Study Sessions",
        value: studySessions,
        trend: 4.8,
        icon: <BookOpen className="h-4 w-4" />,
      },
      {
        label: "Life Score Trend",
        value: Math.round(score),
        trend: trendValue,
        icon: <Activity className="h-4 w-4" />,
      },
      {
        label: "XP This Week",
        value: xpWeek,
        trend: 8.2,
        icon: <Sparkles className="h-4 w-4" />,
      },
    ];
  }, [energyForecast, gamificationProfile?.weekly_momentum, habits, lifeScore?.component_scores?.sleep, plan?.blocks, score, trendValue]);

  return (
    <div className="space-y-6">
      {error ? <InsightBanner text={error} type="danger" /> : null}

      <AppCard padding="lg" className="flex flex-col justify-between gap-6 lg:flex-row lg:items-center">
        <div>
          <h2 className="page-title">Good morning, {todayName}</h2>
          <p className="meta-copy mt-2">{format(new Date(), "EEEE, MMMM do yyyy")}</p>
        </div>
        <div className="flex items-center gap-4">
          <ProgressRing value={score} size="lg" label="Life Score" sublabel={lifeExplanation} />
        </div>
      </AppCard>

      <AppCard>
        <p className="section-label">Today&apos;s Priority Actions</p>
        <div className="mt-4 flex flex-wrap gap-2">
          <QuickActionButton
            icon={<Target className="h-4 w-4" />}
            label="Check In Habit"
            shortcut="Cmd K"
            onClick={() => navigate("/habits")}
          />
          <QuickActionButton
            icon={<Pill className="h-4 w-4" />}
            label="Log Medicine"
            shortcut="Cmd K"
            onClick={() => navigate("/medicine")}
          />
          <QuickActionButton
            icon={<NotebookPen className="h-4 w-4" />}
            label="Write Journal"
            shortcut="Cmd K"
            onClick={() => navigate("/journal")}
          />
          <QuickActionButton
            icon={<Moon className="h-4 w-4" />}
            label="Log Sleep"
            shortcut="Cmd K"
            onClick={() => navigate("/sleep")}
          />
          <QuickActionButton
            icon={<Dumbbell className="h-4 w-4" />}
            label="Log Workout"
            shortcut="Cmd K"
            onClick={() => navigate("/fitness")}
          />
        </div>
      </AppCard>

      <AppCard>
        <div className="flex items-center justify-between gap-3">
          <div>
            <p className="section-label">Morning Briefing</p>
            <p className="meta-copy mt-1">{format(new Date(), "PPP")}</p>
          </div>
          <button
            type="button"
            className="rounded-lg border border-border px-3 py-1.5 text-xs text-text-secondary"
            onClick={() => setBriefingOpen((prev) => !prev)}
          >
            {briefingOpen ? "Collapse" : "Expand"}
          </button>
        </div>

        {briefingOpen ? (
          <div className="mt-4 space-y-3">
            <InsightBanner
              type="info"
              text={briefing?.ai_recommendation_of_day || "No recommendation yet. Start your first check-in to unlock guidance."}
            />
            {warnings.slice(0, 5).map((warning) => (
              <InsightBanner
                key={warning.id}
                type={warning.severity === "critical" ? "danger" : warning.severity === "high" ? "warning" : "info"}
                text={`${warning.warning_type.replace(/_/g, " ")}: ${warning.explanation}`}
                dismissible
              />
            ))}
            <div className="grid gap-2 md:grid-cols-2 lg:grid-cols-3">
              <AppCard padding="sm" className="bg-surface-raised">
                <p className="section-label">Sleep</p>
                <p className="meta-copy mt-1">{score > 0 ? `Sleep component score: ${Math.round(lifeScore?.component_scores?.sleep ?? 0)}` : "No sleep summary available"}</p>
              </AppCard>
              <AppCard padding="sm" className="bg-surface-raised">
                <p className="section-label">Schedule</p>
                <p className="meta-copy mt-1">{scheduleRows.length} blocks today</p>
              </AppCard>
              <AppCard padding="sm" className="bg-surface-raised">
                <p className="section-label">Habits</p>
                <p className="meta-copy mt-1">{briefing?.priority_habits?.length ?? 0} priority habits</p>
              </AppCard>
              <AppCard padding="sm" className="bg-surface-raised">
                <p className="section-label">Medicines</p>
                <p className="meta-copy mt-1">{reminders.length} upcoming reminders</p>
              </AppCard>
              <AppCard padding="sm" className="bg-surface-raised md:col-span-2 lg:col-span-2">
                <p className="section-label">Energy Prediction</p>
                <p className="meta-copy mt-1">
                  Peak hours: {(briefing?.energy_prediction?.peak_hours || []).join(", ") || "N/A"}
                </p>
              </AppCard>
            </div>
          </div>
        ) : null}
      </AppCard>

      <motion.section variants={staggerContainer} initial="initial" animate="animate" className="grid gap-6 lg:grid-cols-5">
        <motion.div variants={fadeMotion} className="lg:col-span-3">
          <AppCard>
            <p className="section-label">Today&apos;s Schedule</p>
            <div className="mt-4 max-h-[420px] space-y-2 overflow-y-auto pr-1">
              {loading ? (
                <SkeletonLoader variant="card" />
              ) : scheduleRows.length === 0 ? (
                <p className="body-copy">No schedule blocks yet.</p>
              ) : (
                scheduleRows.map((block) => (
                  <TimelineCard
                    key={block.id}
                    time={`${block.start_time.slice(0, 5)}-${block.end_time.slice(0, 5)}`}
                    title={block.title}
                    category={block.category}
                    status={block.status === "in_progress" ? "active" : block.status === "completed" ? "done" : "pending"}
                    duration={`${block.estimated_duration_minutes || 0} min`}
                  />
                ))
              )}
            </div>
          </AppCard>
        </motion.div>

        <motion.div variants={fadeMotion} className="lg:col-span-2">
          <AppCard>
            <p className="section-label">Activity Feed</p>
            <div className="mt-4 max-h-[420px] space-y-2 overflow-y-auto pr-1">
              {loading ? (
                <SkeletonLoader variant="text" lines={8} />
              ) : feedRows.length === 0 ? (
                <p className="body-copy">No activity yet.</p>
              ) : (
                feedRows.map((item) => (
                  <div key={item.event_id} className="rounded-lg border border-border bg-surface-raised p-3">
                    <p className="section-label">{item.module}</p>
                    <p className="mt-1 text-sm text-text-primary">{item.summary}</p>
                    <p className="meta-copy mt-1">{item.timestamp}</p>
                  </div>
                ))
              )}
            </div>
          </AppCard>
        </motion.div>
      </motion.section>

      <motion.section variants={staggerContainer} initial="initial" animate="animate" className="overflow-x-auto">
        <div className="grid min-w-[1100px] grid-cols-6 gap-3">
          {loading
            ? Array.from({ length: 6 }).map((_, idx) => <SkeletonLoader key={idx} variant="stat" />)
            : summaryStats.map((item) => (
                <motion.div key={item.label} variants={fadeMotion}>
                  <StatCard
                    label={item.label}
                    value={item.value}
                    unit={item.unit}
                    trend={item.trend}
                    trendLabel="vs last week"
                    icon={item.icon}
                  />
                </motion.div>
              ))}
        </div>
      </motion.section>

      <motion.section variants={staggerContainer} initial="initial" animate="animate">
        <AppCard className="relative overflow-hidden bg-gradient-to-br from-surface to-surface-raised border-accent/20">
          <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <p className="text-sm font-semibold capitalize text-accent flex items-center gap-2">
                <Bot className="h-4 w-4" /> OS Agent
              </p>
              <p className="mt-1 text-sm text-text-primary">
                {agentStatuses.length > 0 && typeof (agentStatuses[0] as any).last_message_preview === 'string' 
                   ? (agentStatuses[0] as any).last_message_preview 
                   : "I am ready to manage your day. How can I help?"}
              </p>
            </div>
            
            <button
               onClick={() => navigate('/chat')}
               className="shrink-0 rounded-lg bg-accent px-4 py-2 text-sm font-semibold text-white transition hover:bg-accent-hover"
            >
               Open Chat
            </button>
          </div>
          
          <div className="mt-4 flex flex-wrap gap-2">
            {[
              "How am I doing?",
              "Reschedule my day",
              "Log sleep",
              "Morning briefing"
            ].map(prompt => (
               <button
                 key={prompt}
                 onClick={() => {
                   navigate('/chat', { state: { prefill: prompt } });
                 }}
                 className="rounded-full border border-border bg-background px-3 py-1.5 text-xs font-medium text-text-secondary transition hover:border-accent hover:text-accent"
               >
                 {prompt}
               </button>
            ))}
          </div>
        </AppCard>
      </motion.section>
    </div>
  );
}
