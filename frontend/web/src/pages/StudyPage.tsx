import { motion, useReducedMotion } from "framer-motion";
import { Brain, Clock3, Play, RotateCcw, Sparkles, Target } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { fadeInUp, reduceMotion, staggerContainer } from "../lib/animations";
import { api } from "../services/api";
import { MockTest, RevisionCard, StudyDashboard, Subject } from "../types/api";
import { AppCard, EmptyState, ProgressRing, SectionHeader, SkeletonLoader, StatCard } from "../components/ui";

export default function StudyPage() {
  const [subjects, setSubjects] = useState<Subject[]>([]);
  const [cardsDue, setCardsDue] = useState<RevisionCard[]>([]);
  const [mocks, setMocks] = useState<MockTest[]>([]);
  const [progress, setProgress] = useState<Array<Record<string, unknown>>>([]);
  const [dashboard, setDashboard] = useState<StudyDashboard | null>(null);
  const [suggestion, setSuggestion] = useState<Record<string, unknown> | null>(null);
  const [planRows, setPlanRows] = useState<Array<Record<string, unknown>>>([]);
  const [planDate, setPlanDate] = useState(() => new Date().toISOString().slice(0, 10));
  const [dailyHours, setDailyHours] = useState(4);
  const [selectedSubjectId, setSelectedSubjectId] = useState("");
  const [quickSessionTopic, setQuickSessionTopic] = useState("Revision Sprint");
  const [secondsLeft, setSecondsLeft] = useState(25 * 60);
  const [running, setRunning] = useState(false);
  const [loading, setLoading] = useState(true);
  const [planning, setPlanning] = useState(false);
  const [reviewingCardId, setReviewingCardId] = useState<string | null>(null);
  const [expandedCardId, setExpandedCardId] = useState<string | null>(null);
  const [error, setError] = useState("");

  const shouldReduceMotion = useReducedMotion();
  const fadeMotion = reduceMotion(shouldReduceMotion, fadeInUp);

  const load = async () => {
    setLoading(true);
    setError("");
    try {
      const [subjectList, dueCards, mockTests, progressRows, dashboardData, suggestionData] = await Promise.all([
        api.study.listSubjects(),
        api.study.cardsDue(),
        api.study.listMocks({ limit: 10, offset: 0 }),
        api.study.progress(),
        api.study.dashboard(),
        api.study.suggest(),
      ]);

      setSubjects(subjectList);
      setCardsDue(dueCards);
      setMocks(mockTests);
      setProgress(progressRows);
      setDashboard(dashboardData);
      setSuggestion(suggestionData);

      if (!selectedSubjectId && subjectList[0]) {
        setSelectedSubjectId(subjectList[0].id);
      }
    } catch {
      setError("Unable to load study intelligence right now.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void load();
  }, []);

  useEffect(() => {
    if (!running) {
      return;
    }

    const timer = window.setInterval(() => {
      setSecondsLeft((prev) => {
        if (prev <= 1) {
          window.clearInterval(timer);
          setRunning(false);
          return 0;
        }
        return prev - 1;
      });
    }, 1000);

    return () => window.clearInterval(timer);
  }, [running]);

  const timerLabel = useMemo(() => {
    const minutes = Math.floor(secondsLeft / 60)
      .toString()
      .padStart(2, "0");
    const seconds = (secondsLeft % 60).toString().padStart(2, "0");
    return `${minutes}:${seconds}`;
  }, [secondsLeft]);

  const progressPct = useMemo(() => Math.max(0, Math.min(100, (1 - secondsLeft / (25 * 60)) * 100)), [secondsLeft]);

  const streak = useMemo(() => Math.max(1, Math.min(30, mocks.length * 2)), [mocks.length]);

  const onPomodoroComplete = async () => {
    if (!selectedSubjectId) {
      return;
    }
    try {
      await api.study.createSession({
        subject_id: selectedSubjectId,
        duration_minutes: 25,
        topics_covered: [quickSessionTopic || "Pomodoro focus block"],
        comprehension_score: 4,
        session_date: new Date().toISOString().slice(0, 10),
      });
      setSecondsLeft(25 * 60);
      await load();
    } catch {
      setError("Could not log completed pomodoro session.");
    }
  };

  useEffect(() => {
    if (secondsLeft === 0) {
      void onPomodoroComplete();
    }
  }, [secondsLeft]);

  const onCreateStarterSubject = async () => {
    try {
      await api.study.createSubject({
        name: "General Revision",
        syllabus_topics: ["Starter topic"],
        total_weight: 1,
        color: "#3B82F6",
      });
      await load();
    } catch {
      setError("Failed to create starter subject.");
    }
  };

  const onGeneratePlan = async () => {
    setPlanning(true);
    setError("");
    try {
      const plan = await api.study.plan({ target_date: planDate, daily_hours: dailyHours });
      setPlanRows(plan);
    } catch {
      setError("Could not generate study plan right now.");
    } finally {
      setPlanning(false);
    }
  };

  const onReviewCard = async (cardId: string, quality: number) => {
    setReviewingCardId(cardId);
    try {
      await api.study.reviewCard(cardId, quality);
      await load();
    } catch {
      setError("Unable to save revision card review.");
    } finally {
      setReviewingCardId(null);
    }
  };

  const onQuickLogSession = async () => {
    if (!selectedSubjectId) {
      return;
    }
    try {
      await api.study.createSession({
        subject_id: selectedSubjectId,
        duration_minutes: 45,
        topics_covered: [quickSessionTopic || "Focused revision"],
        comprehension_score: 5,
        session_date: new Date().toISOString().slice(0, 10),
      });
      await load();
    } catch {
      setError("Unable to log quick study session.");
    }
  };

  return (
    <div className="space-y-6">
      <SectionHeader
        title="Study"
        subtitle="Deliberate sessions, spaced repetition, and focus-aware scheduling."
      />

      {error ? <p className="rounded-lg border border-danger/40 bg-danger/10 px-3 py-2 text-sm text-danger">{error}</p> : null}

      <motion.section variants={staggerContainer} initial="initial" animate="animate" className="grid gap-4 lg:grid-cols-3">
        <motion.div variants={fadeMotion} className="lg:col-span-2 grid gap-4 md:grid-cols-2">
          <StatCard
            label="Cards Due Today"
            value={dashboard?.cards_due_today ?? cardsDue.length}
            trend={6.3}
            trendLabel="from yesterday"
          />
          <StatCard label="Current Streak" value={streak} unit="days" trend={2.1} trendLabel="focus cadence" />
        </motion.div>

        <motion.div variants={fadeMotion}>
          <AppCard className="h-full text-center">
            <p className="section-label">Pomodoro Timer</p>
            <div className="mt-3 flex items-center justify-center">
              <ProgressRing value={progressPct} label={timerLabel} sublabel="25 minute cycle" />
            </div>
            <div className="mt-4 flex justify-center gap-2">
              <button
                type="button"
                onClick={() => setRunning(true)}
                className="inline-flex items-center gap-1 rounded-button bg-accent px-3 py-1.5 text-xs font-semibold text-white"
              >
                <Play className="h-3.5 w-3.5" /> Start
              </button>
              <button
                type="button"
                onClick={() => {
                  setRunning(false);
                  setSecondsLeft(25 * 60);
                }}
                className="inline-flex items-center gap-1 rounded-button border border-border px-3 py-1.5 text-xs text-text-secondary"
              >
                <RotateCcw className="h-3.5 w-3.5" /> Reset
              </button>
            </div>
          </AppCard>
        </motion.div>
      </motion.section>

      {loading ? (
        <div className="space-y-2">
          {Array.from({ length: 3 }).map((_, idx) => (
            <SkeletonLoader key={idx} variant="card" />
          ))}
        </div>
      ) : subjects.length === 0 ? (
        <EmptyState
          icon={<Clock3 className="h-6 w-6" />}
          title="No study subjects yet"
          description="Create a subject to start tracking due cards, timer sessions, and progress trends."
          action={
            <button
              type="button"
              onClick={() => void onCreateStarterSubject()}
              className="rounded-button bg-accent px-4 py-2 text-sm font-semibold text-white"
            >
              Create Subject
            </button>
          }
        />
      ) : (
        <>
          <motion.section variants={staggerContainer} initial="initial" animate="animate" className="grid gap-4 lg:grid-cols-2">
            <motion.div variants={fadeMotion}>
              <AppCard>
                <p className="section-label">AI Recommendation</p>
                <div className="mt-3 rounded-lg border border-border bg-surface-raised p-3">
                  <p className="text-sm text-text-primary">
                    {String((suggestion && suggestion.recommendation) || "No recommendation available yet.")}
                  </p>
                  <p className="mt-2 text-xs text-text-muted">
                    Subject: {String((suggestion && suggestion.subject) || "n/a")} | Cards due: {String((suggestion && suggestion.cards_due) || 0)}
                  </p>
                </div>

                <div className="mt-4 grid gap-2 md:grid-cols-[1fr_auto]">
                  <select
                    value={selectedSubjectId}
                    onChange={(event) => setSelectedSubjectId(event.target.value)}
                    className="rounded-input border border-border bg-surface-raised px-3 py-2 text-sm"
                  >
                    {subjects.map((subject) => (
                      <option key={subject.id} value={subject.id}>
                        {subject.name}
                      </option>
                    ))}
                  </select>
                  <button
                    type="button"
                    onClick={() => void onQuickLogSession()}
                    className="inline-flex items-center justify-center gap-1 rounded-button border border-border px-3 py-2 text-xs text-text-secondary"
                  >
                    <Target className="h-3.5 w-3.5" /> Log 45m Session
                  </button>
                </div>
                <input
                  value={quickSessionTopic}
                  onChange={(event) => setQuickSessionTopic(event.target.value)}
                  placeholder="Quick session topic"
                  className="mt-2 w-full rounded-input border border-border bg-surface-raised px-3 py-2 text-sm"
                />
              </AppCard>
            </motion.div>

            <motion.div variants={fadeMotion}>
              <AppCard>
                <p className="section-label">Generate Plan</p>
                <div className="mt-3 grid gap-2 md:grid-cols-2">
                  <input
                    type="date"
                    value={planDate}
                    onChange={(event) => setPlanDate(event.target.value)}
                    className="rounded-input border border-border bg-surface-raised px-3 py-2 text-sm"
                  />
                  <input
                    type="number"
                    min={1}
                    max={16}
                    value={dailyHours}
                    onChange={(event) => setDailyHours(Number(event.target.value) || 1)}
                    className="rounded-input border border-border bg-surface-raised px-3 py-2 text-sm"
                  />
                </div>
                <button
                  type="button"
                  onClick={() => void onGeneratePlan()}
                  disabled={planning}
                  className="mt-3 inline-flex items-center gap-1 rounded-button bg-accent px-3 py-2 text-xs font-semibold text-white disabled:opacity-50"
                >
                  <Sparkles className="h-3.5 w-3.5" /> {planning ? "Generating..." : "Generate AI Plan"}
                </button>

                {planRows.length > 0 ? (
                  <div className="mt-3 space-y-2">
                    {planRows.slice(0, 4).map((row, index) => (
                      <div key={index} className="rounded-lg border border-border bg-surface-raised p-2 text-xs">
                        <p className="font-medium text-text-primary">{String(row.title || "Study Block")}</p>
                        <p className="text-text-muted">
                          {String(row.start_time || "--:--")} - {String(row.end_time || "--:--")} | Priority {String(row.priority || 2)}
                        </p>
                      </div>
                    ))}
                  </div>
                ) : null}
              </AppCard>
            </motion.div>
          </motion.section>

          <AppCard>
            <p className="section-label">Mock Test Scores</p>
            <div className="mt-4 h-56">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={mocks.map((mock) => ({ name: mock.test_name.slice(0, 12), score: mock.percentage }))}>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(148,163,184,0.2)" />
                  <XAxis dataKey="name" tick={{ fill: "rgb(var(--color-text-muted))", fontSize: 11 }} />
                  <YAxis tick={{ fill: "rgb(var(--color-text-muted))", fontSize: 11 }} domain={[0, 100]} />
                  <Tooltip />
                  <Bar dataKey="score" fill="rgb(var(--color-accent))" radius={[8, 8, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </AppCard>

          <motion.section variants={staggerContainer} initial="initial" animate="animate" className="grid gap-4 lg:grid-cols-2">
            <motion.div variants={fadeMotion}>
              <AppCard>
                <p className="section-label">Subject Progress</p>
                <div className="mt-4 space-y-3">
                  {progress.map((row, index) => {
                    const subject = String(row.subject || `Subject ${index + 1}`);
                    const cards = Number(row.cards_due || 0);
                    const hours = Number(row.hours_studied || 0);
                    const pct = Math.max(5, Math.min(100, Math.round((hours / Math.max(hours + cards, 1)) * 100)));
                    return (
                      <div key={`${subject}-${index}`}>
                        <div className="mb-1 flex items-center justify-between text-sm">
                          <span className="text-text-primary">{subject}</span>
                          <span className="meta-copy">{pct}%</span>
                        </div>
                        <div className="h-2 rounded-full bg-surface-raised">
                          <div className="h-2 rounded-full bg-accent" style={{ width: `${pct}%` }} />
                        </div>
                      </div>
                    );
                  })}
                </div>
              </AppCard>
            </motion.div>

            <motion.div variants={fadeMotion}>
              <AppCard>
                <p className="section-label">Focus Bar</p>
                <p className="meta-copy mt-1">Energy to focus mapping for the current cycle</p>
                <div className="mt-4 h-4 rounded-full bg-surface-raised">
                  <div className="h-4 rounded-full bg-gradient-to-r from-warning via-accent to-success" style={{ width: `${100 - progressPct}%` }} />
                </div>
                <p className="meta-copy mt-3">Deep focus is strongest in the first 15 minutes of each active cycle.</p>
                <div className="mt-3 rounded-lg border border-border bg-surface-raised p-3 text-xs text-text-secondary">
                  <p className="inline-flex items-center gap-1 font-semibold text-text-primary">
                    <Brain className="h-3.5 w-3.5 text-accent" /> Weekly momentum
                  </p>
                  <p className="mt-1">
                    {dashboard ? `${dashboard.study_minutes_last_7d} minutes in the last 7 days, avg comprehension ${dashboard.avg_comprehension_last_7d}/10.` : "No weekly data yet."}
                  </p>
                </div>
              </AppCard>
            </motion.div>
          </motion.section>

          <AppCard>
            <p className="section-label">Due Cards Drill</p>
            {cardsDue.length === 0 ? (
              <p className="mt-3 text-sm text-text-muted">No cards due. You are ahead of schedule.</p>
            ) : (
              <div className="mt-3 space-y-3">
                {cardsDue.slice(0, 6).map((card) => (
                  <div key={card.id} className="rounded-lg border border-border bg-surface-raised p-3">
                    <p className="text-sm font-medium text-text-primary">Q: {card.question}</p>
                    {expandedCardId === card.id ? <p className="mt-2 text-sm text-text-secondary">A: {card.answer}</p> : null}
                    <div className="mt-3 flex flex-wrap items-center gap-2">
                      <button
                        type="button"
                        onClick={() => setExpandedCardId((prev) => (prev === card.id ? null : card.id))}
                        className="rounded-button border border-border px-2 py-1 text-xs text-text-secondary"
                      >
                        {expandedCardId === card.id ? "Hide answer" : "Show answer"}
                      </button>
                      {[2, 3, 4, 5].map((quality) => (
                        <button
                          key={quality}
                          type="button"
                          onClick={() => void onReviewCard(card.id, quality)}
                          disabled={reviewingCardId === card.id}
                          className="rounded-button bg-accent/15 px-2 py-1 text-xs text-accent disabled:opacity-50"
                        >
                          {reviewingCardId === card.id ? "Saving..." : `Rate ${quality}`}
                        </button>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </AppCard>
        </>
      )}
    </div>
  );
}
