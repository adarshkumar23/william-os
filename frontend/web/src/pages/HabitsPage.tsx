import { addDays, format } from "date-fns";
import { Plus } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import HabitCard from "../components/HabitCard";
import Modal from "../components/Modal";
import { api } from "../services/api";
import { Habit, HabitCheckIn } from "../types/api";

const heatmapDays = Array.from({ length: 7 }).map((_, index) => addDays(new Date(), index - 6));

export default function HabitsPage() {
  const [habits, setHabits] = useState<Habit[]>([]);
  const [checkedToday, setCheckedToday] = useState<Record<string, boolean>>({});
  const [openAdd, setOpenAdd] = useState(false);
  const [newHabit, setNewHabit] = useState({
    name: "",
    icon: "✅",
    category: "general",
    frequency: "daily",
    auto_schedule: true,
  });

  const load = async () => {
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

  const procrastinationStatus = useMemo(() => {
    const completed = Object.values(checkedToday).filter(Boolean).length;
    if (completed >= Math.max(1, Math.floor(habits.length * 0.7))) {
      return "Low procrastination risk";
    }
    if (completed >= Math.max(1, Math.floor(habits.length * 0.4))) {
      return "Moderate procrastination risk";
    }
    return "High procrastination risk";
  }, [checkedToday, habits.length]);

  return (
    <div className="space-y-6">
      <header className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Habits</h1>
          <p className="text-sm text-[rgb(var(--text-dim))]">Build consistency with streak-aware check-ins.</p>
        </div>
        <button
          type="button"
          onClick={() => setOpenAdd(true)}
          className="inline-flex items-center gap-2 rounded-xl bg-[rgb(var(--primary))] px-4 py-2 text-sm font-semibold text-white"
        >
          <Plus className="h-4 w-4" /> Add Habit
        </button>
      </header>

      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {habits.map((habit) => (
          <HabitCard
            key={habit.id}
            habit={habit}
            checkedToday={Boolean(checkedToday[habit.id])}
            onToggle={onToggleHabit}
          />
        ))}
      </section>

      <section className="card p-4">
        <h2 className="text-lg font-semibold">Weekly completion heatmap</h2>
        <div className="mt-4 overflow-x-auto">
          <table className="w-full min-w-[560px] border-collapse">
            <thead>
              <tr>
                <th className="pb-2 text-left text-xs text-[rgb(var(--text-dim))]">Habit</th>
                {heatmapDays.map((day) => (
                  <th key={day.toISOString()} className="pb-2 text-center text-xs text-[rgb(var(--text-dim))]">
                    {format(day, "EEE")}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {habits.map((habit) => (
                <tr key={habit.id}>
                  <td className="py-2 text-sm font-medium">{habit.name}</td>
                  {heatmapDays.map((day) => {
                    const isToday = format(day, "yyyy-MM-dd") === format(new Date(), "yyyy-MM-dd");
                    const done = isToday ? Boolean(checkedToday[habit.id]) : (habit.current_streak ?? 0) > 0;
                    return (
                      <td key={day.toISOString()} className="py-2 text-center">
                        <span
                          className={`inline-block h-5 w-5 rounded ${
                            done ? "bg-emerald-500/80" : "bg-[rgb(var(--bg-muted))]"
                          }`}
                        />
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section className="card p-4">
        <h2 className="text-lg font-semibold">Procrastination detection</h2>
        <p className="mt-2 text-sm text-[rgb(var(--text-dim))]">{procrastinationStatus}</p>
      </section>

      <Modal
        open={openAdd}
        title="Add Habit"
        onClose={() => setOpenAdd(false)}
        footer={
          <div className="flex justify-end gap-2">
            <button
              type="button"
              className="rounded-lg border border-[rgb(var(--border))] px-3 py-2 text-sm"
              onClick={() => setOpenAdd(false)}
            >
              Cancel
            </button>
            <button
              type="button"
              className="rounded-lg bg-[rgb(var(--primary))] px-3 py-2 text-sm font-semibold text-white"
              onClick={() => void onCreateHabit()}
            >
              Create Habit
            </button>
          </div>
        }
      >
        <div className="grid gap-3 sm:grid-cols-2">
          <label className="block space-y-1">
            <span className="text-sm font-medium">Name</span>
            <input
              value={newHabit.name}
              onChange={(event) => setNewHabit((prev) => ({ ...prev, name: event.target.value }))}
              className="w-full rounded-xl border border-[rgb(var(--border))] bg-[rgb(var(--bg-muted))] px-3 py-2"
            />
          </label>
          <label className="block space-y-1">
            <span className="text-sm font-medium">Icon</span>
            <input
              value={newHabit.icon}
              onChange={(event) => setNewHabit((prev) => ({ ...prev, icon: event.target.value }))}
              className="w-full rounded-xl border border-[rgb(var(--border))] bg-[rgb(var(--bg-muted))] px-3 py-2"
            />
          </label>
          <label className="block space-y-1">
            <span className="text-sm font-medium">Category</span>
            <input
              value={newHabit.category}
              onChange={(event) => setNewHabit((prev) => ({ ...prev, category: event.target.value }))}
              className="w-full rounded-xl border border-[rgb(var(--border))] bg-[rgb(var(--bg-muted))] px-3 py-2"
            />
          </label>
          <label className="block space-y-1">
            <span className="text-sm font-medium">Frequency</span>
            <select
              value={newHabit.frequency}
              onChange={(event) => setNewHabit((prev) => ({ ...prev, frequency: event.target.value }))}
              className="w-full rounded-xl border border-[rgb(var(--border))] bg-[rgb(var(--bg-muted))] px-3 py-2"
            >
              <option value="daily">Daily</option>
              <option value="weekdays">Weekdays</option>
              <option value="weekends">Weekends</option>
            </select>
          </label>
        </div>
      </Modal>
    </div>
  );
}
