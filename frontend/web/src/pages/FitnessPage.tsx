import { format } from "date-fns";
import { motion, useReducedMotion } from "framer-motion";
import { Activity, Footprints, HeartPulse, Plus } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { fadeInUp, reduceMotion, staggerContainer } from "../lib/animations";
import { api } from "../services/api";
import { EnergyForecast, Workout } from "../types/api";
import { AppCard, EmptyState, ProgressRing, SectionHeader, SkeletonLoader, StatCard } from "../components/ui";

export default function FitnessPage() {
  const [summary, setSummary] = useState<Record<string, unknown> | null>(null);
  const [energy, setEnergy] = useState<EnergyForecast | null>(null);
  const [workouts, setWorkouts] = useState<Workout[]>([]);
  const [suggestions, setSuggestions] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);

  const shouldReduceMotion = useReducedMotion();
  const fadeMotion = reduceMotion(shouldReduceMotion, fadeInUp);

  const load = async () => {
    setLoading(true);
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
    setLoading(false);
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
      <SectionHeader title="Fitness" subtitle="Energy-aware movement and recovery signals across your day." />

      <motion.section variants={staggerContainer} initial="initial" animate="animate" className="grid gap-4 md:grid-cols-2">
        <motion.div variants={fadeMotion}>
          <StatCard label="Step Count" value={Number(summary?.steps ?? 0)} trend={2.8} icon={<Footprints className="h-4 w-4" />} />
        </motion.div>
        <motion.div variants={fadeMotion}>
          <StatCard label="Energy Score" value={Number(summary?.energy_score ?? 70)} trend={1.6} icon={<HeartPulse className="h-4 w-4" />} />
        </motion.div>
      </motion.section>

      {loading ? (
        <SkeletonLoader variant="card" />
      ) : (
        <AppCard>
          <p className="section-label">Energy Curve</p>
          <div className="mt-4 h-64">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={energyPoints}>
                <defs>
                  <linearGradient id="energyFill" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="rgb(var(--color-accent))" stopOpacity={0.45} />
                    <stop offset="95%" stopColor="rgb(var(--color-accent))" stopOpacity={0.02} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(148,163,184,0.2)" />
                <XAxis dataKey="hour" tick={{ fill: "rgb(var(--color-text-muted))", fontSize: 11 }} />
                <YAxis domain={[0, 10]} tick={{ fill: "rgb(var(--color-text-muted))", fontSize: 11 }} />
                <Tooltip />
                <Area type="monotone" dataKey="score" stroke="rgb(var(--color-accent))" fill="url(#energyFill)" strokeWidth={2.5} />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </AppCard>
      )}

      <motion.section variants={staggerContainer} initial="initial" animate="animate" className="grid gap-4 lg:grid-cols-3">
        <motion.div variants={fadeMotion} className="lg:col-span-2">
          {workouts.length === 0 ? (
            <EmptyState
              icon={<Activity className="h-6 w-6" />}
              title="No workouts logged"
              description="Log your first workout to unlock richer movement analysis."
              action={
                <button
                  type="button"
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
                  className="inline-flex items-center gap-1 rounded-button bg-accent px-4 py-2 text-sm font-semibold text-white"
                >
                  <Plus className="h-4 w-4" /> Log Workout
                </button>
              }
            />
          ) : (
            <AppCard>
              <p className="section-label">Workout Log</p>
              <div className="mt-4 space-y-2">
                {workouts.map((workout) => (
                  <div key={workout.id} className="flex items-center justify-between rounded-lg border border-border bg-surface-raised p-3">
                    <div>
                      <p className="text-sm font-medium text-text-primary">{workout.activity}</p>
                      <p className="meta-copy">{workout.workout_date}</p>
                    </div>
                    <p className="text-sm text-text-secondary">
                      {workout.duration_minutes} min • {workout.calories_burned} cal
                    </p>
                  </div>
                ))}
              </div>
            </AppCard>
          )}
        </motion.div>

        <motion.div variants={fadeMotion}>
          <AppCard>
            <p className="section-label">Progress Rings</p>
            <div className="mt-4 space-y-4">
              <ProgressRing value={Math.min(100, Math.round((Number(summary?.steps || 0) / 10000) * 100))} label="Steps" />
              <ProgressRing value={Math.min(100, Math.round((Number(summary?.calories || 0) / 800) * 100))} color="rgb(var(--color-warning))" label="Calories" />
              <ProgressRing value={Math.min(100, Math.round((Number(summary?.heart_rate || 70) / 180) * 100))} color="rgb(var(--color-danger))" label="Heart Rate Zones" />
            </div>
          </AppCard>
        </motion.div>
      </motion.section>

      <AppCard>
        <p className="section-label">AI Optimization Notes</p>
        <div className="mt-3 space-y-2">
          {suggestions.length > 0 ? (
            suggestions.map((tip, index) => (
              <p key={`${tip}-${index}`} className="rounded-lg bg-surface-raised px-3 py-2 text-sm text-text-secondary">
                {tip}
              </p>
            ))
          ) : (
            <p className="body-copy">No suggestions yet.</p>
          )}
        </div>
      </AppCard>
    </div>
  );
}
