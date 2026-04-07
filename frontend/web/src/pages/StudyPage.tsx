import { motion, useReducedMotion } from "framer-motion";
import { Clock3, Play, RotateCcw } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { fadeInUp, reduceMotion, staggerContainer } from "../lib/animations";
import { api } from "../services/api";
import { MockTest, RevisionCard, Subject } from "../types/api";
import { AnimatedCounter, AppCard, EmptyState, ProgressRing, SectionHeader, SkeletonLoader, StatCard } from "../components/ui";

export default function StudyPage() {
  const [subjects, setSubjects] = useState<Subject[]>([]);
  const [cardsDue, setCardsDue] = useState<RevisionCard[]>([]);
  const [mocks, setMocks] = useState<MockTest[]>([]);
  const [progress, setProgress] = useState<Array<Record<string, unknown>>>([]);
  const [secondsLeft, setSecondsLeft] = useState(25 * 60);
  const [running, setRunning] = useState(false);
  const [loading, setLoading] = useState(true);

  const shouldReduceMotion = useReducedMotion();
  const fadeMotion = reduceMotion(shouldReduceMotion, fadeInUp);

  const load = async () => {
    setLoading(true);
    const [subjectList, dueCards, mockTests, progressRows] = await Promise.all([
      api.study.listSubjects(),
      api.study.cardsDue(),
      api.study.listMocks({ limit: 10, offset: 0 }),
      api.study.progress(),
    ]);

    setSubjects(subjectList);
    setCardsDue(dueCards);
    setMocks(mockTests);
    setProgress(progressRows);
    setLoading(false);
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

  const onPomodoroComplete = async () => {
    if (!subjects[0]) {
      return;
    }
    await api.study.createSession({
      subject_id: subjects[0].id,
      duration_minutes: 25,
      topics_covered: ["Pomodoro focus block"],
      comprehension_score: 4,
      session_date: new Date().toISOString().slice(0, 10),
    });
    setSecondsLeft(25 * 60);
    await load();
  };

  useEffect(() => {
    if (secondsLeft === 0) {
      void onPomodoroComplete();
    }
  }, [secondsLeft]);

  const onCreateStarterSubject = async () => {
    await api.study.createSubject({
      name: "General Revision",
      syllabus_topics: ["Starter topic"],
      total_weight: 1,
      color: "#3B82F6",
    });
    await load();
  };

  const streak = useMemo(() => Math.max(1, Math.min(30, mocks.length * 2)), [mocks.length]);

  return (
    <div className="space-y-6">
      <SectionHeader
        title="Study"
        subtitle="Deliberate sessions, spaced repetition, and focus-aware scheduling."
      />

      <motion.section variants={staggerContainer} initial="initial" animate="animate" className="grid gap-4 lg:grid-cols-3">
        <motion.div variants={fadeMotion} className="lg:col-span-2 grid gap-4 md:grid-cols-2">
          <StatCard label="Cards Due Today" value={cardsDue.length} trend={6.3} trendLabel="from yesterday" />
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
              </AppCard>
            </motion.div>
          </motion.section>
        </>
      )}
    </div>
  );
}
