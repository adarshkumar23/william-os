import { format, formatDistanceToNow } from "date-fns";
import {
  BookOpen,
  CircleOff,
  Brain,
  CheckCircle2,
  Clock3,
  Dumbbell,
  GraduationCap,
  MoonStar,
  Pill,
  Scale,
  Sparkles,
  TrendingUp,
} from "lucide-react";
import { useEffect, useMemo, useRef } from "react";

import { ActivityFeedItem } from "../types/api";

type Props = {
  items: ActivityFeedItem[];
  loading: boolean;
  loadingMore: boolean;
  hasMore: boolean;
  onLoadMore: () => Promise<void>;
};

function formatWhen(timestamp: string) {
  const parsed = new Date(timestamp);
  if (Number.isNaN(parsed.getTime())) {
    return timestamp;
  }
  return `${formatDistanceToNow(parsed, { addSuffix: true })} • ${format(parsed, "MMM d, HH:mm")}`;
}

function iconForKey(iconKey: string) {
  switch (iconKey) {
    case "habit_completed":
      return CheckCircle2;
    case "journal_written":
      return BookOpen;
    case "sleep_logged":
      return MoonStar;
    case "medicine_taken":
      return Pill;
    case "medicine_missed":
      return CircleOff;
    case "trade_closed":
      return TrendingUp;
    case "workout_completed":
      return Dumbbell;
    case "study_session_completed":
      return GraduationCap;
    case "decision_made":
      return Scale;
    case "xp_earned":
      return Sparkles;
    case "life_score_changed":
      return Brain;
    default:
      return Clock3;
  }
}

export default function ActivityFeed({ items, loading, loadingMore, hasMore, onLoadMore }: Props) {
  const scrollRootRef = useRef<HTMLDivElement | null>(null);
  const sentinelRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    const root = scrollRootRef.current;
    const sentinel = sentinelRef.current;

    if (!root || !sentinel) {
      return;
    }

    const observer = new IntersectionObserver(
      (entries) => {
        const first = entries[0];
        if (first?.isIntersecting && hasMore && !loading && !loadingMore) {
          void onLoadMore();
        }
      },
      {
        root,
        rootMargin: "0px 0px 220px 0px",
        threshold: 0.1,
      },
    );

    observer.observe(sentinel);
    return () => observer.disconnect();
  }, [hasMore, loading, loadingMore, onLoadMore, items.length]);

  const body = useMemo(() => {
    if (loading && items.length === 0) {
      return <p className="text-sm text-[rgb(var(--text-dim))]">Loading recent activity...</p>;
    }

    if (!loading && items.length === 0) {
      return <p className="text-sm text-[rgb(var(--text-dim))]">No activity yet. Start logging your day.</p>;
    }

    return (
      <div ref={scrollRootRef} className="max-h-[28rem] space-y-2 overflow-y-auto pr-1">
        {items.map((item) => {
          const Icon = iconForKey(item.icon_key);
          return (
            <article
              key={item.event_id}
              className="rounded-xl border border-[rgb(var(--border))] bg-[rgb(var(--bg-muted))] p-3"
            >
              <div className="flex items-start gap-3">
                <span className="mt-0.5 inline-flex h-8 w-8 items-center justify-center rounded-lg bg-[rgb(var(--bg-elevated))]">
                  <Icon className="h-4 w-4" />
                </span>
                <div className="min-w-0 flex-1">
                  <div className="flex items-center justify-between gap-2">
                    <p className="text-xs font-semibold uppercase tracking-wide text-[rgb(var(--text-dim))]">{item.module}</p>
                    <p className="text-xs text-[rgb(var(--text-dim))]">{formatWhen(item.timestamp)}</p>
                  </div>
                  <p className="mt-1 text-sm leading-relaxed">{item.summary}</p>
                  {typeof item.xp_earned === "number" ? (
                    <p className="mt-2 text-xs font-semibold text-[rgb(var(--success))]">+{item.xp_earned} XP</p>
                  ) : null}
                </div>
              </div>
            </article>
          );
        })}

        <div ref={sentinelRef} className="h-1 w-full" />

        {loadingMore ? (
          <p className="pt-1 text-center text-xs text-[rgb(var(--text-dim))]">Loading more...</p>
        ) : hasMore ? (
          <p className="pt-1 text-center text-xs text-[rgb(var(--text-dim))]">Scroll to load more</p>
        ) : (
          <p className="pt-1 text-center text-xs text-[rgb(var(--text-dim))]">You are all caught up.</p>
        )}
      </div>
    );
  }, [hasMore, items, loading, loadingMore]);

  return (
    <section className="card p-4">
      <div className="mb-3 flex items-center justify-between">
        <h3 className="text-sm font-semibold">Activity feed</h3>
        <span className="text-xs text-[rgb(var(--text-dim))]">Unified timeline</span>
      </div>
      {body}
    </section>
  );
}
