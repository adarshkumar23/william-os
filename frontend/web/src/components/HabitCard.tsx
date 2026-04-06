import { motion } from "framer-motion";
import { CheckCircle2, Flame, Circle } from "lucide-react";
import clsx from "clsx";

import { Habit } from "../types/api";

type HabitCardProps = {
  habit: Habit;
  checkedToday: boolean;
  onToggle: (habit: Habit, nextChecked: boolean) => Promise<void>;
};

export default function HabitCard({ habit, checkedToday, onToggle }: HabitCardProps) {
  return (
    <motion.article
      layout
      whileHover={{ y: -3 }}
      className={clsx("card p-4 transition", checkedToday ? "ring-2 ring-[rgb(var(--success))]/40" : "")}
    >
      <div className="mb-3 flex items-start justify-between gap-3">
        <div>
          <p className="text-xl">{habit.icon || "✅"}</p>
          <h3 className="mt-1 text-lg font-semibold">{habit.name}</h3>
          <p className="mt-1 text-xs text-[rgb(var(--text-dim))]">{habit.category || "general"}</p>
        </div>
        <div className="rounded-xl bg-[rgb(var(--bg-muted))] px-2 py-1 data-font text-xs">
          <span className="inline-flex items-center gap-1">
            <Flame className="h-3.5 w-3.5 text-amber-400" /> {habit.current_streak ?? 0}
          </span>
        </div>
      </div>

      <button
        type="button"
        onClick={() => void onToggle(habit, !checkedToday)}
        className={clsx(
          "w-full rounded-xl border px-3 py-2 text-sm font-semibold transition",
          checkedToday
            ? "border-[rgb(var(--success))]/50 bg-[rgb(var(--success))]/10 text-[rgb(var(--success))]"
            : "border-[rgb(var(--border))] bg-[rgb(var(--bg-muted))] text-[rgb(var(--text-dim))]",
        )}
      >
        <span className="inline-flex items-center gap-2">
          {checkedToday ? <CheckCircle2 className="h-4 w-4" /> : <Circle className="h-4 w-4" />}
          {checkedToday ? "Checked in" : "Mark done"}
        </span>
      </button>
    </motion.article>
  );
}
