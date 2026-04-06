import { useEffect, useState } from "react";

import MedicineCard from "../components/MedicineCard";
import { api } from "../services/api";

export default function MedicinePage() {
  const [medicines, setMedicines] = useState<any[]>([]);
  const [upcoming, setUpcoming] = useState<any[]>([]);
  const [adherence, setAdherence] = useState<any | null>(null);

  const load = async () => {
    const [medicineData, upcomingData, adherenceData] = await Promise.all([
      api.medicine.list(),
      api.medicine.upcoming().catch(() => []),
      api.medicine.adherence().catch(() => null),
    ]);
    setMedicines(medicineData);
    setUpcoming(upcomingData);
    setAdherence(adherenceData);
  };

  useEffect(() => {
    void load();
  }, []);

  return (
    <div className="space-y-5">
      <section className="panel p-5">
        <h1 className="font-display text-3xl font-bold">Medicine Intelligence</h1>
        <p className="mt-1 text-sm text-slate-600 dark:text-slate-300">
          Upcoming reminders: {upcoming.length} • Adherence: {adherence?.adherence_rate ?? 0}%
        </p>
        <div className="mt-3 h-3 rounded-full bg-slate-200 dark:bg-slate-700">
          <div
            className="h-3 rounded-full bg-gradient-to-r from-william-electric to-william-mint"
            style={{ width: `${Math.min(100, adherence?.adherence_rate || 0)}%` }}
          />
        </div>
      </section>

      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {medicines.map((medicine) => (
          <MedicineCard
            key={medicine.id}
            medicine={medicine}
            onTake={async () => {
              await api.medicine.log(medicine.id, { taken: true, skipped: false });
              await load();
            }}
            onSkip={async () => {
              await api.medicine.log(medicine.id, {
                taken: false,
                skipped: true,
                skip_reason: "Skipped from web app",
              });
              await load();
            }}
          />
        ))}
      </section>
    </div>
  );
}
