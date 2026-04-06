import { useEffect, useMemo, useState } from "react";

import HabitCard from "../components/HabitCard";
import { api } from "../services/api";

export default function HabitsPage() {
  const [habits, setHabits] = useState<any[]>([]);
  const [checkedToday, setCheckedToday] = useState<Record<string, boolean>>({});

  const today = useMemo(() => new Date().toISOString().slice(0, 10), []);

  const load = async () => {
    const [habitData, checkIns] = await Promise.all([
      api.habits.list(),
      api.habits.dailyCheckIns(today).catch(() => []),
    ]);
    setHabits(habitData);

    const map: Record<string, boolean> = {};
    for (const item of checkIns) {
      map[item.habit_id] = !!item.completed;
    }
    setCheckedToday(map);
  };

  useEffect(() => {
    void load();
  }, []);

  return (
    <div className="space-y-5">
      <section className="panel p-5">
        <h1 className="font-display text-3xl font-bold">Habit Engine</h1>
        <p className="mt-1 text-sm text-slate-600 dark:text-slate-300">Check in, protect streaks, and build consistency.</p>
      </section>

      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {habits.map((habit) => (
          <div key={habit.id}>
            <HabitCard
              habit={habit}
              onCheckIn={async () => {
                await api.habits.checkIn(habit.id);
                await load();
              }}
            />
            {checkedToday[habit.id] && (
              <p className="mt-2 text-sm font-semibold text-william-mint">Checked in today</p>
            )}
          </div>
        ))}
      </section>
    </div>
  );
}
