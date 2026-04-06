import { format } from "date-fns";
import { useEffect, useMemo, useState } from "react";
import { Activity, Flame, Footprints, HeartPulse, Moon } from "lucide-react";
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import ChartWrapper from "../components/ChartWrapper";
import StatCard from "../components/StatCard";
import { api } from "../services/api";
import { EnergyForecast, Workout } from "../types/api";

export default function FitnessPage() {
  const [summary, setSummary] = useState<Record<string, unknown> | null>(null);
  const [energy, setEnergy] = useState<EnergyForecast | null>(null);
  const [workouts, setWorkouts] = useState<Workout[]>([]);
  const [suggestions, setSuggestions] = useState<string[]>([]);

  const load = async () => {
    const today = format(new Date(), "yyyy-MM-dd");
    const [dailySummary, forecast, workoutRows, suggestionRows] = await Promise.all([
      api.fitness.summary(today).catch(() => null),
      api.fitness.energyByDate(today).catch(() => null),
      api.fitness.listWorkouts(14),
      api.fitness.suggestions(today).catch(() => []),
    ]);

    setSummary(dailySummary);
    setEnergy(forecast);
    setWorkouts(workoutRows);
    setSuggestions(suggestionRows);
  };

  useEffect(() => {
    void load();
  }, []);

  const energyPoints = useMemo(() => {
    const hourly = (energy?.hourly_scores || {}) as Record<string, number>;
    return Object.entries(hourly)
      .map(([hour, value]) => ({ hour, score: Number(value) }))
      .sort((a, b) => a.hour.localeCompare(b.hour));
  }, [energy]);

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-bold">Fitness Intelligence</h1>
        <p className="text-sm text-[rgb(var(--text-dim))]">Body metrics, energy forecasting, and workout optimization.</p>
      </header>

      <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard icon={Footprints} label="Steps" value={String(summary?.steps ?? "0")} trend="today" />
        <StatCard icon={HeartPulse} label="Heart Rate" value={`${summary?.heart_rate ?? "--"} bpm`} trend="live" />
        <StatCard icon={Flame} label="Calories" value={String(summary?.calories ?? "0")} trend="burned" tone="warning" />
        <StatCard icon={Moon} label="Sleep Hours" value={String(summary?.sleep_hours ?? "--")} trend="last night" tone="success" />
      </section>

      <ChartWrapper title="Energy forecast" subtitle="Predicted energy curve for today">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={energyPoints}>
            <CartesianGrid strokeDasharray="3 3" stroke="rgba(148,163,184,0.2)" />
            <XAxis dataKey="hour" tick={{ fill: "rgb(var(--text-dim))", fontSize: 11 }} />
            <YAxis domain={[0, 10]} tick={{ fill: "rgb(var(--text-dim))", fontSize: 11 }} />
            <Tooltip />
            <Line type="monotone" dataKey="score" stroke="rgb(var(--primary))" strokeWidth={2.5} dot={{ r: 3 }} />
          </LineChart>
        </ResponsiveContainer>
      </ChartWrapper>

      <section className="grid gap-4 lg:grid-cols-2">
        <article className="card p-4">
          <h2 className="text-lg font-semibold">Workout log</h2>
          <div className="mt-3 space-y-2">
            {workouts.map((workout) => (
              <div key={workout.id} className="rounded-xl border border-[rgb(var(--border))] bg-[rgb(var(--bg-muted))] p-3">
                <p className="text-sm font-medium">{workout.activity}</p>
                <p className="text-xs text-[rgb(var(--text-dim))]">
                  {workout.duration_minutes} min • {workout.workout_date}
                </p>
              </div>
            ))}
            {workouts.length === 0 ? <p className="text-sm text-[rgb(var(--text-dim))]">No workouts logged yet.</p> : null}
          </div>
          <button
            type="button"
            className="mt-3 rounded-xl bg-[rgb(var(--primary))] px-3 py-2 text-sm font-semibold text-white"
            onClick={() =>
              void api.fitness
                .logWorkout({
                  activity: "Focus walk",
                  duration_minutes: 30,
                  calories_burned: 120,
                  workout_date: format(new Date(), "yyyy-MM-dd"),
                })
                .then(load)
            }
          >
            Log Workout
          </button>
        </article>

        <article className="card p-4">
          <h2 className="text-lg font-semibold">Optimization suggestions</h2>
          <div className="mt-3 space-y-2 text-sm">
            {suggestions.length > 0 ? (
              suggestions.map((tip, index) => (
                <div key={`${tip}-${index}`} className="rounded-xl bg-[rgb(var(--bg-muted))] p-3">
                  <Activity className="mr-2 inline h-4 w-4 text-[rgb(var(--success))]" />
                  {tip}
                </div>
              ))
            ) : (
              <p className="text-[rgb(var(--text-dim))]">No AI tips yet. Generate an energy forecast first.</p>
            )}
          </div>
        </article>
      </section>
    </div>
  );
}
