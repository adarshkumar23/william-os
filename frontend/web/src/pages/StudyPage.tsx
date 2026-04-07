import { useEffect, useMemo, useState } from "react";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Clock3, Play, RotateCcw } from "lucide-react";

import ChartWrapper from "../components/ChartWrapper";
import EmptyStatePanel from "../components/EmptyStatePanel";
import FlashCard from "../components/FlashCard";
import { api } from "../services/api";
import { MockTest, RevisionCard, Subject } from "../types/api";

export default function StudyPage() {
  const [subjects, setSubjects] = useState<Subject[]>([]);
  const [cardsDue, setCardsDue] = useState<RevisionCard[]>([]);
  const [mocks, setMocks] = useState<MockTest[]>([]);
  const [progress, setProgress] = useState<Array<Record<string, unknown>>>([]);
  const [secondsLeft, setSecondsLeft] = useState(25 * 60);
  const [running, setRunning] = useState(false);

  const load = async () => {
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

  const onCardRate = async (cardId: string, quality: number) => {
    await api.study.reviewCard(cardId, quality);
    await load();
  };

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

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-bold">Study Mentor</h1>
        <p className="text-sm text-[rgb(var(--text-dim))]">Revision, timer flow, and progress analytics.</p>
      </header>

      {subjects.length === 0 ? (
        <EmptyStatePanel
          title="No Study Subjects Yet"
          description="This section helps you track sessions, revision cards, mock scores, and momentum over time."
          ctaLabel="Create your first subject"
          onCta={() => void onCreateStarterSubject()}
          moduleKey="study"
        />
      ) : (
        <section className="card p-4">
          <h2 className="mb-3 text-lg font-semibold">Subjects</h2>
          <div className="flex gap-3 overflow-x-auto pb-1">
            {subjects.map((subject, index) => (
              <article key={subject.id} className="min-w-[220px] rounded-xl border border-[rgb(var(--border))] bg-[rgb(var(--bg-muted))] p-3">
                <div
                  className="mb-2 h-1 rounded-full"
                  style={{ background: ["#3B82F6", "#10B981", "#F59E0B", "#F43F5E"][index % 4] }}
                />
                <p className="text-sm font-semibold">{subject.name}</p>
              </article>
            ))}
          </div>
        </section>
      )}

      <section className="grid gap-4 lg:grid-cols-2">
        <div className="space-y-4">
          <h2 className="text-lg font-semibold">Revision cards due</h2>
          {cardsDue[0] ? (
            <FlashCard
              question={cardsDue[0].question}
              answer={cardsDue[0].answer}
              onRate={(quality) => onCardRate(cardsDue[0].id, quality)}
            />
          ) : (
            <div className="card p-6 text-sm text-[rgb(var(--text-dim))]">No cards due today.</div>
          )}
        </div>

        <article className="card p-4">
          <h2 className="text-lg font-semibold">Pomodoro timer</h2>
          <p className="mt-1 text-sm text-[rgb(var(--text-dim))]">25 min focus / 5 min reset</p>
          <div className="mt-6 text-center">
            <p className="data-font text-6xl font-bold">{timerLabel}</p>
          </div>
          <div className="mt-5 flex items-center justify-center gap-2">
            <button
              type="button"
              onClick={() => setRunning(true)}
              className="inline-flex items-center gap-2 rounded-xl bg-[rgb(var(--primary))] px-4 py-2 text-sm font-semibold text-white"
            >
              <Play className="h-4 w-4" /> Start
            </button>
            <button
              type="button"
              onClick={() => {
                setRunning(false);
                setSecondsLeft(25 * 60);
              }}
              className="inline-flex items-center gap-2 rounded-xl border border-[rgb(var(--border))] px-4 py-2 text-sm"
            >
              <RotateCcw className="h-4 w-4" /> Reset
            </button>
          </div>
          <p className="mt-4 text-center text-xs text-[rgb(var(--text-dim))]">
            <Clock3 className="mr-1 inline h-3.5 w-3.5" /> Session logs automatically when completed.
          </p>
        </article>
      </section>

      <section className="grid gap-4 lg:grid-cols-2">
        <ChartWrapper title="Mock test scores" subtitle="Recent attempts">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={mocks.map((mock) => ({ name: mock.test_name.slice(0, 12), score: mock.percentage }))}>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(148,163,184,0.2)" />
              <XAxis dataKey="name" tick={{ fill: "rgb(var(--text-dim))", fontSize: 11 }} />
              <YAxis tick={{ fill: "rgb(var(--text-dim))", fontSize: 11 }} domain={[0, 100]} />
              <Tooltip />
              <Bar dataKey="score" fill="rgb(var(--primary))" radius={[8, 8, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </ChartWrapper>

        <ChartWrapper title="Progress overview" subtitle="Hours and cards due by subject">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart
              data={progress.map((row) => ({
                subject: String(row.subject ?? "N/A").slice(0, 10),
                hours: Number(row.hours_studied ?? 0),
                cards: Number(row.cards_due ?? 0),
              }))}
            >
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(148,163,184,0.2)" />
              <XAxis dataKey="subject" tick={{ fill: "rgb(var(--text-dim))", fontSize: 11 }} />
              <YAxis tick={{ fill: "rgb(var(--text-dim))", fontSize: 11 }} />
              <Tooltip />
              <Bar dataKey="hours" stackId="a" fill="rgb(var(--primary))" />
              <Bar dataKey="cards" stackId="a" fill="rgb(var(--success))" />
            </BarChart>
          </ResponsiveContainer>
        </ChartWrapper>
      </section>
    </div>
  );
}
