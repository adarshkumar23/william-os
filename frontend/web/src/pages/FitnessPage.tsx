import { useEffect, useMemo, useState } from "react";

import { api } from "../services/api";

export default function FitnessPage() {
  const [summary, setSummary] = useState<any | null>(null);
  const [forecast, setForecast] = useState<any | null>(null);

  const today = useMemo(() => new Date().toISOString().slice(0, 10), []);

  const load = async () => {
    const [summaryData, forecastData] = await Promise.all([
      api.fitness.summary(today).catch(() => null),
      api.fitness.energy(today).catch(() => null),
    ]);
    setSummary(summaryData);
    setForecast(forecastData);
  };

  useEffect(() => {
    void load();
  }, []);

  return (
    <div className="space-y-5">
      <section className="panel p-5">
        <h1 className="font-display text-3xl font-bold">Fitness Intelligence</h1>
        <p className="mt-1 text-sm text-slate-600 dark:text-slate-300">
          Today's health markers and energy projection.
        </p>
      </section>

      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <div className="panel p-4"><p className="text-xs text-slate-500">Steps</p><p className="text-2xl font-bold">{summary?.steps ?? 0}</p></div>
        <div className="panel p-4"><p className="text-xs text-slate-500">Avg HR</p><p className="text-2xl font-bold">{summary?.avg_heart_rate ?? 0}</p></div>
        <div className="panel p-4"><p className="text-xs text-slate-500">Calories</p><p className="text-2xl font-bold">{summary?.calories ?? 0}</p></div>
        <div className="panel p-4"><p className="text-xs text-slate-500">Sleep</p><p className="text-2xl font-bold">{summary?.sleep_hours ?? 0}h</p></div>
      </section>

      <section className="panel p-5">
        <div className="mb-3 flex items-center justify-between">
          <h2 className="font-display text-xl font-bold">Energy Forecast</h2>
          <button
            className="btn-primary"
            onClick={async () => {
              await api.fitness.generateEnergy(today);
              await load();
            }}
            type="button"
          >
            Generate
          </button>
        </div>

        {forecast ? (
          <>
            <p className="text-sm text-slate-600 dark:text-slate-300">
              Peak hours: {forecast.peak_hours?.join(", ") || "N/A"}
            </p>
            <div className="mt-3 grid grid-cols-4 gap-2 md:grid-cols-8">
              {Object.entries(forecast.hourly_scores || {}).map(([hour, score]) => (
                <div key={hour} className="rounded-lg border border-slate-200 p-2 text-center text-sm dark:border-slate-700">
                  <p className="text-xs text-slate-500">{hour}:00</p>
                  <p className="font-semibold">{String(score)}</p>
                </div>
              ))}
            </div>
          </>
        ) : (
          <p className="text-sm text-slate-500">No forecast generated yet.</p>
        )}
      </section>
    </div>
  );
}
