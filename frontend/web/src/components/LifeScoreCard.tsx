import { Activity } from "lucide-react";
import { Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import type { LifeScore, LifeScoreHistoryPoint } from "../types/api";

const COMPONENT_LABELS: Record<string, string> = {
  sleep: "Sleep",
  habits: "Habits",
  fitness: "Fitness",
  study: "Study",
  medicine: "Medicine",
  journal: "Journal",
  decisions: "Decisions",
};

type LifeScoreCardProps = {
  lifeScore: LifeScore | null;
  history: LifeScoreHistoryPoint[];
  loading: boolean;
};

function gaugeTone(score: number) {
  if (score >= 80) {
    return "rgb(var(--success))";
  }
  if (score >= 60) {
    return "rgb(var(--warning))";
  }
  return "rgb(var(--danger))";
}

export default function LifeScoreCard({ lifeScore, history, loading }: LifeScoreCardProps) {
  const score = lifeScore?.score ?? 0;
  const normalized = Math.max(0, Math.min(100, score));
  const radius = 48;
  const circumference = 2 * Math.PI * radius;
  const dashOffset = circumference - (normalized / 100) * circumference;
  const tone = gaugeTone(normalized);

  const chartData = history.map((point) => ({
    date: new Date(point.computed_at).toLocaleDateString(undefined, { month: "short", day: "numeric" }),
    score: Math.round(point.score * 10) / 10,
  }));

  return (
    <section className="card p-4">
      <header className="mb-3 flex items-center justify-between">
        <div>
          <h3 className="text-base font-semibold">Life Score</h3>
          <p className="text-xs text-[rgb(var(--text-dim))]">Composite health index from cross-module signals.</p>
        </div>
        <Activity className="h-5 w-5 text-[rgb(var(--primary))]" />
      </header>

      {loading ? (
        <div className="text-sm text-[rgb(var(--text-dim))]">Computing Life Score...</div>
      ) : !lifeScore ? (
        <div className="text-sm text-[rgb(var(--text-dim))]">Life Score unavailable right now.</div>
      ) : (
        <>
          <div className="grid gap-4 md:grid-cols-[auto,1fr]">
            <div className="flex items-center justify-center">
              <div className="relative h-36 w-36">
                <svg viewBox="0 0 120 120" className="h-full w-full -rotate-90">
                  <circle cx="60" cy="60" r={radius} stroke="rgb(var(--bg-muted))" strokeWidth="10" fill="none" />
                  <circle
                    cx="60"
                    cy="60"
                    r={radius}
                    stroke={tone}
                    strokeWidth="10"
                    fill="none"
                    strokeLinecap="round"
                    strokeDasharray={circumference}
                    strokeDashoffset={dashOffset}
                    style={{ transition: "stroke-dashoffset 400ms ease" }}
                  />
                </svg>
                <div className="absolute inset-0 flex flex-col items-center justify-center">
                  <p className="data-font text-3xl font-bold">{Math.round(score)}</p>
                  <p className="text-xs text-[rgb(var(--text-dim))]">/ 100</p>
                </div>
              </div>
            </div>

            <div>
              <p className="mb-2 text-sm leading-relaxed text-[rgb(var(--text-dim))]">{lifeScore.explanation}</p>
              <div className="space-y-2">
                {Object.entries(lifeScore.component_scores)
                  .sort((a, b) => b[1] - a[1])
                  .map(([key, value]) => {
                    const width = `${Math.max(0, Math.min(100, value))}%`;
                    return (
                      <div key={key}>
                        <div className="mb-1 flex items-center justify-between text-xs">
                          <span>{COMPONENT_LABELS[key] ?? key}</span>
                          <span className="data-font">{Math.round(value)}</span>
                        </div>
                        <div className="h-2 rounded-full bg-[rgb(var(--bg-muted))]">
                          <div
                            className="h-2 rounded-full bg-[rgb(var(--primary))]"
                            style={{ width }}
                            aria-label={`${key} component score ${Math.round(value)}`}
                          />
                        </div>
                      </div>
                    );
                  })}
              </div>
            </div>
          </div>

          <div className="mt-4 h-44 rounded-xl bg-[rgb(var(--bg-muted))] p-2">
            {chartData.length > 0 ? (
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={chartData}>
                  <XAxis dataKey="date" tick={{ fontSize: 11 }} stroke="rgb(var(--text-dim))" />
                  <YAxis domain={[0, 100]} tick={{ fontSize: 11 }} stroke="rgb(var(--text-dim))" />
                  <Tooltip />
                  <Line
                    type="monotone"
                    dataKey="score"
                    stroke="rgb(var(--primary))"
                    strokeWidth={2.5}
                    dot={false}
                    name="Life Score"
                  />
                </LineChart>
              </ResponsiveContainer>
            ) : (
              <div className="flex h-full items-center justify-center text-xs text-[rgb(var(--text-dim))]">
                No trend data yet.
              </div>
            )}
          </div>
        </>
      )}
    </section>
  );
}
