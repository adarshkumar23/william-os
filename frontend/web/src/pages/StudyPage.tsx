import { FormEvent, useEffect, useState } from "react";

import { api } from "../services/api";

export default function StudyPage() {
  const [subjects, setSubjects] = useState<any[]>([]);
  const [progress, setProgress] = useState<any[]>([]);
  const [cardsDue, setCardsDue] = useState<any[]>([]);

  const [subjectId, setSubjectId] = useState("");
  const [duration, setDuration] = useState(60);
  const [comprehension, setComprehension] = useState(7);

  const load = async () => {
    const [subjectData, progressData, dueData] = await Promise.all([
      api.study.subjects().catch(() => []),
      api.study.progress().catch(() => []),
      api.study.cardsDue().catch(() => []),
    ]);
    setSubjects(subjectData);
    setProgress(progressData);
    setCardsDue(dueData);
    if (!subjectId && subjectData.length > 0) {
      setSubjectId(subjectData[0].id);
    }
  };

  useEffect(() => {
    void load();
  }, []);

  const handleLogSession = async (event: FormEvent) => {
    event.preventDefault();
    if (!subjectId) {
      return;
    }

    await api.study.logSession({
      subject_id: subjectId,
      duration_minutes: duration,
      comprehension_score: comprehension,
      topics_covered: ["Session logged from web"],
      session_date: new Date().toISOString().slice(0, 10),
    });

    await load();
  };

  return (
    <div className="grid gap-5 lg:grid-cols-[1.2fr_1fr]">
      <section className="space-y-5">
        <div className="panel p-5">
          <h1 className="font-display text-3xl font-bold">IAS Study Mentor</h1>
          <p className="mt-1 text-sm text-slate-600 dark:text-slate-300">Cards due today: {cardsDue.length}</p>
        </div>

        <div className="panel p-4">
          <h2 className="font-display text-xl font-bold">Progress by Subject</h2>
          <div className="mt-3 space-y-2">
            {progress.map((item) => (
              <div key={item.subject} className="rounded-xl border border-slate-200 p-3 dark:border-slate-700">
                <p className="font-semibold">{item.subject}</p>
                <p className="text-sm text-slate-600 dark:text-slate-300">
                  Hours: {item.hours_studied} • Comprehension: {item.avg_comprehension} • Cards due: {item.cards_due} • Mock avg: {item.mock_avg}%
                </p>
              </div>
            ))}
          </div>
        </div>
      </section>

      <aside className="panel p-4">
        <h2 className="font-display text-xl font-bold">Log Study Session</h2>
        <form className="mt-3 space-y-3" onSubmit={handleLogSession}>
          <select
            className="w-full rounded-xl border border-slate-300 bg-white/80 p-2 dark:border-slate-700 dark:bg-slate-900"
            value={subjectId}
            onChange={(event) => setSubjectId(event.target.value)}
          >
            {subjects.map((subject) => (
              <option key={subject.id} value={subject.id}>
                {subject.name}
              </option>
            ))}
          </select>
          <input
            className="w-full rounded-xl border border-slate-300 bg-white/80 p-2 dark:border-slate-700 dark:bg-slate-900"
            type="number"
            min={15}
            max={480}
            value={duration}
            onChange={(event) => setDuration(Number(event.target.value))}
          />
          <input
            className="w-full rounded-xl border border-slate-300 bg-white/80 p-2 dark:border-slate-700 dark:bg-slate-900"
            type="number"
            min={1}
            max={10}
            value={comprehension}
            onChange={(event) => setComprehension(Number(event.target.value))}
          />
          <button className="btn-primary w-full" type="submit">
            Save Session
          </button>
        </form>
      </aside>
    </div>
  );
}
