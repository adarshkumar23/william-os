import { Activity, ChevronRight, Gauge, Trophy } from "lucide-react";

import { GamificationProfile } from "../types/api";

type Props = {
  profile: GamificationProfile | null;
  loading: boolean;
};

export default function GamificationPanel({ profile, loading }: Props) {
  if (loading && !profile) {
    return <section className="card p-4 text-sm text-[rgb(var(--text-dim))]">Loading progression profile...</section>;
  }

  if (!profile) {
    return <section className="card p-4 text-sm text-[rgb(var(--text-dim))]">Gamification data unavailable.</section>;
  }

  const topRecords = profile.records.slice(0, 3);

  return (
    <section className="card p-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.2em] text-[rgb(var(--text-dim))]">Progression</p>
          <h3 className="mt-1 text-lg font-semibold">Level {profile.level_progress.level}</h3>
          <p className="text-sm text-[rgb(var(--text-dim))]">{profile.level_progress.total_xp.toLocaleString()} XP total</p>
        </div>
        <Trophy className="h-5 w-5 text-[rgb(var(--warning))]" />
      </div>

      <div className="mt-3">
        <div className="mb-1 flex items-center justify-between text-xs text-[rgb(var(--text-dim))]">
          <span>{profile.level_progress.current_level_xp_floor.toLocaleString()} XP</span>
          <span>{profile.level_progress.next_level_xp_target.toLocaleString()} XP</span>
        </div>
        <div className="h-2 rounded-full bg-[rgb(var(--bg-muted))]">
          <div
            className="h-2 rounded-full bg-[rgb(var(--primary))] transition-all duration-500"
            style={{ width: `${Math.max(0, Math.min(100, profile.level_progress.progress_pct))}%` }}
          />
        </div>
        <p className="mt-1 text-xs text-[rgb(var(--text-dim))]">{profile.level_progress.xp_to_next_level.toLocaleString()} XP to next level</p>
      </div>

      <div className="mt-4 grid grid-cols-2 gap-2 text-sm">
        <div className="rounded-xl bg-[rgb(var(--bg-muted))] p-3">
          <p className="inline-flex items-center gap-1 text-xs uppercase tracking-wide text-[rgb(var(--text-dim))]">
            <Gauge className="h-3.5 w-3.5" /> Momentum
          </p>
          <p className="mt-1 text-lg font-semibold">{profile.weekly_momentum.momentum_score.toFixed(1)}</p>
          <p className="text-xs text-[rgb(var(--text-dim))]">Focus rank #{profile.weekly_momentum.focus_rank}</p>
        </div>
        <div className="rounded-xl bg-[rgb(var(--bg-muted))] p-3">
          <p className="inline-flex items-center gap-1 text-xs uppercase tracking-wide text-[rgb(var(--text-dim))]">
            <Activity className="h-3.5 w-3.5" /> Discipline debt
          </p>
          <p className="mt-1 text-lg font-semibold">{profile.weekly_momentum.discipline_debt.toFixed(1)}</p>
          <p className="text-xs text-[rgb(var(--text-dim))]">XP missed vs weekly expectation</p>
        </div>
      </div>

      <div className="mt-4">
        <p className="text-xs font-semibold uppercase tracking-wide text-[rgb(var(--text-dim))]">Personal records</p>
        <div className="mt-2 space-y-2">
          {topRecords.length > 0 ? (
            topRecords.map((record) => (
              <div key={record.id} className="flex items-center justify-between rounded-xl bg-[rgb(var(--bg-muted))] px-3 py-2">
                <span className="text-sm">{record.record_type.split("_").join(" ")}</span>
                <span className="inline-flex items-center gap-1 text-sm font-semibold">
                  {record.value}
                  <ChevronRight className="h-3.5 w-3.5 text-[rgb(var(--text-dim))]" />
                </span>
              </div>
            ))
          ) : (
            <p className="text-xs text-[rgb(var(--text-dim))]">Records will appear as milestones are achieved.</p>
          )}
        </div>
      </div>
    </section>
  );
}
