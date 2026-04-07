import clsx from "clsx";

import AppCard from "./AppCard";

type TimelineCardProps = {
  time: string;
  title: string;
  category: string;
  status: "pending" | "active" | "done";
  duration?: string;
};

const statusLabel = {
  pending: "Pending",
  active: "Active",
  done: "Done",
};

export default function TimelineCard({ time, title, category, status, duration }: TimelineCardProps) {
  return (
    <div className="grid grid-cols-[72px_1fr] gap-3">
      <div className="pt-3 text-right">
        <p className="meta-copy tabular-nums">{time}</p>
      </div>
      <div className="relative pb-3">
        <span className="absolute left-0 top-0 h-full w-px bg-border-strong" aria-hidden />
        <AppCard
          padding="sm"
          className={clsx(
            "relative ml-4 border-l-2",
            status === "active" ? "border-l-accent bg-surface-raised" : "border-l-border",
          )}
        >
          <div className="flex items-start justify-between gap-3">
            <div>
              <p className="text-sm font-medium text-text-primary">{title}</p>
              <p className="meta-copy mt-1">{category}</p>
            </div>
            <span className="rounded-full border border-border bg-surface-raised px-2 py-1 text-xs text-text-secondary">
              {statusLabel[status]}
            </span>
          </div>
          {duration ? <p className="meta-copy mt-2">{duration}</p> : null}
        </AppCard>
      </div>
    </div>
  );
}
