type Habit = {
  id: string;
  name: string;
  category: string;
  current_streak: number;
  best_streak: number;
  preferred_time?: string | null;
};

export default function HabitCard({ habit, onCheckIn }: { habit: Habit; onCheckIn: () => void }) {
  return (
    <article className="panel p-4 animate-rise">
      <p className="text-xs uppercase tracking-wide text-slate-500 dark:text-slate-400">{habit.category}</p>
      <h3 className="mt-1 font-display text-lg font-bold">{habit.name}</h3>
      <p className="mt-2 text-sm text-slate-600 dark:text-slate-300">
        Streak: {habit.current_streak} • Best: {habit.best_streak}
      </p>
      <button className="btn-primary mt-4 w-full" onClick={onCheckIn} type="button">
        Check In
      </button>
    </article>
  );
}
