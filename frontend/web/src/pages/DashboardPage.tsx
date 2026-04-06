import { useCallback, useEffect, useState } from "react";

import ScheduleTimeline from "../components/ScheduleTimeline";
import { useRealtimeSync } from "../hooks/useRealtimeSync";
import { api } from "../services/api";

export default function DashboardPage() {
  const [schedule, setSchedule] = useState<any | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const plan = await api.schedule.today();
      setSchedule(plan);
    } catch (err: any) {
      setError(err?.response?.data?.error || "Unable to load today's schedule");
    }
  }, []);

  useRealtimeSync({
    onScheduleUpdated: () => {
      void load();
    },
  });

  useEffect(() => {
    void load();
  }, [load]);

  return (
    <div className="space-y-5">
      <section className="panel p-5">
        <p className="text-xs uppercase tracking-[0.2em] text-slate-500 dark:text-slate-400">Today</p>
        <h1 className="font-display text-3xl font-bold">Mission Control</h1>
        {schedule && (
          <p className="mt-2 text-sm text-slate-600 dark:text-slate-300">
            Date: {schedule.plan_date} • Status: {schedule.status} • Day score: {schedule.completion_score ?? "-"}
          </p>
        )}
        {error && <p className="mt-2 text-red-600">{error}</p>}
      </section>

      <ScheduleTimeline blocks={schedule?.blocks || []} />
    </div>
  );
}
