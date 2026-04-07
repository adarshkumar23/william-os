import { addDays, format } from "date-fns";
import { motion, useReducedMotion } from "framer-motion";
import { CheckCircle2, Circle, Flame, Plus } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { Bar, BarChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { fadeInUp, reduceMotion, staggerContainer } from "../lib/animations";
import { api } from "../services/api";
import { Habit, HabitCheckIn } from "../types/api";
import { AnimatedCounter, AppCard, Badge, EmptyState, Modal, SectionHeader, SkeletonLoader } from "../components/ui";

const heatmapDays = Array.from({ length: 7 }).map((_, index) => addDays(new Date(), index - 6));

export default function HabitsPage() {
  const [habits, setHabits] = useState<Habit[]>([]);
  const [checkedToday, setCheckedToday] = useState<Record<string, boolean>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [openAdd, setOpenAdd] = useState(false);
  const [newHabit, setNewHabit] = useState({
    name: "",
    icon: "✅",
    category: "general",
    frequency: "daily",
    auto_schedule: true,
  });

  const shouldReduceMotion = useReducedMotion();
  const fadeMotion = reduceMotion(shouldReduceMotion, fadeInUp);

  const load = async () => {
    setLoading(true);
    setError("");
    try {
      const [habitList, todayCheckins] = await Promise.all([
        api.habits.list({ active_only: true, limit: 200, offset: 0 }),
        api.habits.dailyCheckIns(format(new Date(), "yyyy-MM-dd")).catch(() => [] as HabitCheckIn[]),
      ]);

      const checkedMap = todayCheckins.reduce<Record<string, boolean>>((acc, item) => {
        acc[item.habit_id] = item.completed && !item.skipped;
        return acc;
      }, {});

      setHabits(habitList);
      setCheckedToday(checkedMap);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to load habits");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void load();
  }, []);

  const onToggleHabit = async (habit: Habit, nextChecked: boolean) => {
    await api.habits.checkIn(habit.id, {
      check_date: format(new Date(), "yyyy-MM-dd"),
      completed: nextChecked,
      skipped: !nextChecked,
    });
    setCheckedToday((prev) => ({ ...prev, [habit.id]: nextChecked }));
  };

  const onCreateHabit = async () => {
    await api.habits.create(newHabit);
    setOpenAdd(false);
    setNewHabit({ name: "", icon: "✅", category: "general", frequency: "daily", auto_schedule: true });
    await load();
  };

  const maxStreak = useMemo(() => habits.reduce((max, habit) => Math.max(max, habit.current_streak || 0), 0), [habits]);

  const trendData = useMemo(
    () =>
      heatmapDays.map((day) => {
        const key = format(day, "yyyy-MM-dd");
        const completed = habits.reduce((count, habit) => {
          const isToday = key === format(new Date(), "yyyy-MM-dd");
          const done = isToday ? Boolean(checkedToday[habit.id]) : (habit.current_streak || 0) > 0;
          return count + (done ? 1 : 0);
        }, 0);

        return { day: format(day, "EEE"), completed };
      }),
    [checkedToday, habits],
  );

  return (
    <div className="space-y-6">
      <SectionHeader
        title="Habits"
        subtitle="Build momentum through repeatable wins and low-friction check-ins."
        action={
          <button
            type="button"
            onClick={() => setOpenAdd(true)}
            className="inline-flex items-center gap-2 rounded-button bg-accent px-4 py-2 text-sm font-semibold text-white transition hover:bg-accent-hover"
          >
            <Plus className="h-4 w-4" /> Add Habit
          </button>
        }
      />

      {error ? <p className="text-sm text-danger">{error}</p> : null}

      <motion.section variants={staggerContainer} initial="initial" animate="animate" className="grid gap-4 lg:grid-cols-3">
        <motion.div variants={fadeMotion} className="lg:col-span-1">
          <AppCard hover>
            <p className="section-label">Primary Metric</p>
            <p className="mt-3 text-4xl font-bold tabular-nums text-text-primary">
              <AnimatedCounter value={maxStreak} />
              <span className="ml-2 text-2xl">🔥</span>
            </p>
            <p className="meta-copy mt-2">Current best active streak</p>
          </AppCard>
        </motion.div>

        <motion.div variants={fadeMotion} className="lg:col-span-2">
          <AppCard>
            <p className="section-label">Weekly Completion Trend</p>
            <div className="mt-4 h-56">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={trendData}>
                  <XAxis dataKey="day" stroke="rgb(var(--color-text-muted))" tick={{ fontSize: 11 }} />
                  <YAxis stroke="rgb(var(--color-text-muted))" tick={{ fontSize: 11 }} />
                  <Tooltip />
                  <Bar dataKey="completed" fill="rgb(var(--color-accent))" radius={[6, 6, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </AppCard>
        </motion.div>
      </motion.section>

      {loading ? (
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
          {Array.from({ length: 6 }).map((_, idx) => (
            <SkeletonLoader key={idx} variant="card" />
          ))}
        </div>
      ) : habits.length === 0 ? (
        <EmptyState
          icon={<Flame className="h-6 w-6" />}
          title="No habits yet"
          description="Create your first habit to start tracking streaks and procrastination risk."
          action={
            <button
              type="button"
              onClick={() => setOpenAdd(true)}
              className="rounded-button bg-accent px-4 py-2 text-sm font-semibold text-white"
            >
              Create Habit
            </button>
          }
        />
      ) : (
        <>
          <motion.section variants={staggerContainer} initial="initial" animate="animate" className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
            {habits.map((habit) => {
              const checked = Boolean(checkedToday[habit.id]);
              const risk = (habit.current_streak || 0) < 2 && !checked;

              return (
                <motion.div key={habit.id} variants={fadeMotion}>
                  <AppCard hover className="h-full">
                    <div className="flex items-start justify-between gap-2">
                      <div>
                        <p className="text-lg">{habit.icon || "•"}</p>
                        <h3 className="mt-1 text-base font-semibold text-text-primary">{habit.name}</h3>
                        <p className="meta-copy mt-1">{habit.category || "general"}</p>
                      </div>
                      {risk ? <Badge label="Risk" variant="warning" /> : null}
                    </div>

                    <div className="mt-4 flex items-center justify-between">
                      <p className="meta-copy">Streak: {habit.current_streak || 0}</p>
                      <motion.button
                        type="button"
                        whileTap={shouldReduceMotion ? undefined : { scale: 0.92 }}
                        onClick={() => void onToggleHabit(habit, !checked)}
                        className={`inline-flex items-center gap-1 rounded-button px-3 py-1.5 text-xs font-medium ${
                          checked
                            ? "bg-success/15 text-success"
                            : "border border-border bg-surface-raised text-text-secondary"
                        }`}
                      >
                        {checked ? <CheckCircle2 className="h-4 w-4" /> : <Circle className="h-4 w-4" />}
                        {checked ? "Checked" : "Check in"}
                      </motion.button>
                    </div>
                  </AppCard>
                </motion.div>
              );
            })}
          </motion.section>

          <AppCard>
            <p className="section-label">Weekly Heatmap</p>
            <div className="mt-4 overflow-x-auto">
              <table className="w-full min-w-[560px]">
                <thead>
                  <tr>
                    <th className="pb-2 text-left text-xs text-text-muted">Habit</th>
                    {heatmapDays.map((day) => (
                      <th key={day.toISOString()} className="pb-2 text-center text-xs text-text-muted">
                        {format(day, "EEE")}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {habits.map((habit) => (
                    <tr key={habit.id}>
                      <td className="py-2 text-sm text-text-primary">{habit.name}</td>
                      {heatmapDays.map((day) => {
                        const isToday = format(day, "yyyy-MM-dd") === format(new Date(), "yyyy-MM-dd");
                        const done = isToday ? Boolean(checkedToday[habit.id]) : (habit.current_streak || 0) > 0;
                        return (
                          <td key={day.toISOString()} className="py-2 text-center">
                            <span className={`inline-block h-5 w-5 rounded-sm ${done ? "bg-accent" : "bg-surface-raised"}`} />
                          </td>
                        );
                      })}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </AppCard>
        </>
      )}

      <Modal isOpen={openAdd} onClose={() => setOpenAdd(false)} title="Create Habit" size="md">
        <div className="grid gap-3 sm:grid-cols-2">
          <label className="space-y-1">
            <span className="text-sm text-text-secondary">Name</span>
            <input
              value={newHabit.name}
              onChange={(event) => setNewHabit((prev) => ({ ...prev, name: event.target.value }))}
              className="w-full rounded-input border border-border bg-surface-raised px-3 py-2 text-sm text-text-primary"
            />
          </label>
          <label className="space-y-1">
            <span className="text-sm text-text-secondary">Icon</span>
            <input
              value={newHabit.icon}
              onChange={(event) => setNewHabit((prev) => ({ ...prev, icon: event.target.value }))}
              className="w-full rounded-input border border-border bg-surface-raised px-3 py-2 text-sm text-text-primary"
            />
          </label>
          <label className="space-y-1">
            <span className="text-sm text-text-secondary">Category</span>
            <input
              value={newHabit.category}
              onChange={(event) => setNewHabit((prev) => ({ ...prev, category: event.target.value }))}
              className="w-full rounded-input border border-border bg-surface-raised px-3 py-2 text-sm text-text-primary"
            />
          </label>
          <label className="space-y-1">
            <span className="text-sm text-text-secondary">Frequency</span>
            <select
              value={newHabit.frequency}
              onChange={(event) => setNewHabit((prev) => ({ ...prev, frequency: event.target.value }))}
              className="w-full rounded-input border border-border bg-surface-raised px-3 py-2 text-sm text-text-primary"
            >
              <option value="daily">Daily</option>
              <option value="weekdays">Weekdays</option>
              <option value="weekends">Weekends</option>
            </select>
          </label>
        </div>

        <div className="mt-4 flex justify-end gap-2">
          <button
            type="button"
            className="rounded-button border border-border px-4 py-2 text-sm text-text-secondary"
            onClick={() => setOpenAdd(false)}
          >
            Cancel
          </button>
          <button
            type="button"
            className="rounded-button bg-accent px-4 py-2 text-sm font-semibold text-white"
            onClick={() => void onCreateHabit()}
          >
            Save Habit
          </button>
        </div>
      </Modal>
    </div>
  );
}
