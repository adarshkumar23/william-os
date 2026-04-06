import { motion } from "framer-motion";
import { CheckCircle2, CircleDashed, PlayCircle } from "lucide-react";
import clsx from "clsx";

import { ScheduleBlock } from "../types/api";

const categoryStyle: Record<string, string> = {
  work: "bg-blue-500/15 text-blue-400",
  study: "bg-violet-500/15 text-violet-400",
  fitness: "bg-emerald-500/15 text-emerald-400",
  meal: "bg-amber-500/15 text-amber-400",
  sleep: "bg-indigo-500/15 text-indigo-400",
  break: "bg-slate-500/15 text-slate-300",
  routine: "bg-teal-500/15 text-teal-400",
};

type TimelineBlockProps = {
  block: ScheduleBlock;
  onStart?: (blockId: string) => Promise<void>;
  onComplete?: (blockId: string) => Promise<void>;
};

export default function TimelineBlock({ block, onStart, onComplete }: TimelineBlockProps) {
  const statusIcon =
    block.status === "completed" ? (
      <CheckCircle2 className="h-4 w-4 text-[rgb(var(--success))]" />
    ) : block.status === "in_progress" ? (
      <PlayCircle className="h-4 w-4 text-[rgb(var(--primary))]" />
    ) : (
      <CircleDashed className="h-4 w-4 text-[rgb(var(--text-dim))]" />
    );

  return (
    <motion.article
      layout
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      className="card relative overflow-hidden p-4"
    >
      <div className="absolute left-0 top-0 h-full w-1 bg-[rgb(var(--primary))]" />
      <div className="ml-2 space-y-3">
        <div className="flex items-center justify-between gap-3">
          <div>
            <p className="data-font text-sm text-[rgb(var(--text-dim))]">
              {block.start_time.slice(0, 5)} - {block.end_time.slice(0, 5)}
            </p>
            <h4 className="text-base font-semibold">{block.title}</h4>
          </div>
          <div className="flex items-center gap-2">
            <span
              className={clsx(
                "rounded-full px-2 py-1 text-xs font-medium uppercase",
                categoryStyle[block.category] ?? "bg-slate-500/15 text-slate-300",
              )}
            >
              {block.category}
            </span>
            <span className="rounded-full bg-[rgb(var(--bg-muted))] px-2 py-1 text-xs data-font">P{block.priority}</span>
            {statusIcon}
          </div>
        </div>

        <div className="flex items-center gap-2">
          {block.status === "pending" && onStart ? (
            <button
              type="button"
              className="rounded-lg bg-[rgb(var(--primary))] px-3 py-1.5 text-xs font-semibold text-white"
              onClick={() => void onStart(block.id)}
            >
              Start
            </button>
          ) : null}
          {block.status === "in_progress" && onComplete ? (
            <button
              type="button"
              className="rounded-lg bg-[rgb(var(--success))] px-3 py-1.5 text-xs font-semibold text-slate-900"
              onClick={() => void onComplete(block.id)}
            >
              Complete
            </button>
          ) : null}
        </div>
      </div>
    </motion.article>
  );
}
