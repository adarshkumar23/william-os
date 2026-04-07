import { useEffect, useMemo, useState } from "react";
import { Pie, PieChart, ResponsiveContainer, Cell, Tooltip } from "recharts";
import { Plus, TriangleAlert } from "lucide-react";

import EmptyStatePanel from "../components/EmptyStatePanel";
import MedicineCard from "../components/MedicineCard";
import Modal from "../components/Modal";
import { api } from "../services/api";
import { Medicine, MedicineReminder } from "../types/api";

const COLORS = ["rgb(var(--success))", "rgb(var(--danger))"];

export default function MedicinePage() {
  const [medicines, setMedicines] = useState<Medicine[]>([]);
  const [reminders, setReminders] = useState<MedicineReminder[]>([]);
  const [adherence, setAdherence] = useState<{ total_taken: number; total_skipped: number; adherence_rate: number } | null>(
    null,
  );
  const [refills, setRefills] = useState<Medicine[]>([]);
  const [openAdd, setOpenAdd] = useState(false);
  const [newMedicine, setNewMedicine] = useState({
    name: "",
    dosage: "",
    medicine_type: "supplement",
    reminder_times: ["08:00"],
    times_per_day: 1,
    with_food: false,
    refill_reminder_days: 7,
  });

  const load = async () => {
    const [medicineList, upcoming, adherenceStats, refillList] = await Promise.all([
      api.medicine.list({ limit: 100, offset: 0 }),
      api.medicine.upcoming(720).catch(() => []),
      api.medicine.adherence(30).catch(() => null),
      api.medicine.refills().catch(() => []),
    ]);
    setMedicines(medicineList);
    setReminders(upcoming);
    setAdherence(adherenceStats as { total_taken: number; total_skipped: number; adherence_rate: number } | null);
    setRefills(refillList);
  };

  useEffect(() => {
    void load();
  }, []);

  const onTake = async (medicine: Medicine) => {
    await api.medicine.log(medicine.id, { taken: true, skipped: false });
    await load();
  };

  const onSkip = async (medicine: Medicine, reason: string) => {
    await api.medicine.log(medicine.id, { taken: false, skipped: true, skip_reason: reason });
    await load();
  };

  const reminderMap = useMemo(() => {
    const map = new Map<string, string>();
    reminders.forEach((item) => {
      if (!map.has(item.medicine_name)) {
        map.set(item.medicine_name, item.scheduled_time);
      }
    });
    return map;
  }, [reminders]);

  const chartData = [
    { name: "Taken", value: adherence?.total_taken ?? 0 },
    { name: "Skipped", value: adherence?.total_skipped ?? 0 },
  ];

  const onCreate = async () => {
    await api.medicine.create(newMedicine);
    setOpenAdd(false);
    setNewMedicine({
      name: "",
      dosage: "",
      medicine_type: "supplement",
      reminder_times: ["08:00"],
      times_per_day: 1,
      with_food: false,
      refill_reminder_days: 7,
    });
    await load();
  };

  return (
    <div className="space-y-6">
      <header className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Medicine</h1>
          <p className="text-sm text-[rgb(var(--text-dim))]">Track doses, adherence, and refill risks.</p>
        </div>
        <button
          type="button"
          onClick={() => setOpenAdd(true)}
          className="inline-flex items-center gap-2 rounded-xl bg-[rgb(var(--primary))] px-4 py-2 text-sm font-semibold text-white"
        >
          <Plus className="h-4 w-4" /> Add Medicine
        </button>
      </header>

      {refills.length > 0 ? (
        <section className="space-y-2">
          {refills.map((medicine) => (
            <article key={medicine.id} className="card flex items-center gap-2 border-amber-500/40 bg-amber-500/10 p-3">
              <TriangleAlert className="h-4 w-4 text-amber-400" />
              <p className="text-sm">
                Refill alert: <span className="font-semibold">{medicine.name}</span>
              </p>
            </article>
          ))}
        </section>
      ) : null}

      <section className="grid gap-4 lg:grid-cols-3">
        <div className="space-y-3 lg:col-span-2">
          {medicines.length === 0 ? (
            <EmptyStatePanel
              title="No Medicines Added"
              description="This section tracks adherence trends, upcoming doses, and refill risk." 
              ctaLabel="Log your first medicine"
              onCta={() => setOpenAdd(true)}
              moduleKey="medicine"
            />
          ) : (
            medicines.map((medicine) => (
              <MedicineCard
                key={medicine.id}
                medicine={medicine}
                nextDue={reminderMap.get(medicine.name)}
                onTake={onTake}
                onSkip={onSkip}
              />
            ))
          )}
        </div>

        <article className="card p-4">
          <h3 className="text-lg font-semibold">Adherence (30 days)</h3>
          <p className="mt-1 text-sm text-[rgb(var(--text-dim))]">{adherence?.adherence_rate ?? 0}% taken</p>
          <div className="mt-4 h-56">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie data={chartData} dataKey="value" innerRadius={55} outerRadius={90}>
                  {chartData.map((entry, index) => (
                    <Cell key={entry.name} fill={COLORS[index % COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip />
              </PieChart>
            </ResponsiveContainer>
          </div>
        </article>
      </section>

      <Modal
        open={openAdd}
        title="Add Medicine"
        onClose={() => setOpenAdd(false)}
        footer={
          <div className="flex justify-end gap-2">
            <button
              type="button"
              className="rounded-lg border border-[rgb(var(--border))] px-3 py-2 text-sm"
              onClick={() => setOpenAdd(false)}
            >
              Cancel
            </button>
            <button
              type="button"
              className="rounded-lg bg-[rgb(var(--primary))] px-3 py-2 text-sm font-semibold text-white"
              onClick={() => void onCreate()}
            >
              Save
            </button>
          </div>
        }
      >
        <div className="grid gap-3 md:grid-cols-2">
          <label className="space-y-1">
            <span className="text-sm font-medium">Name</span>
            <input
              value={newMedicine.name}
              onChange={(event) => setNewMedicine((prev) => ({ ...prev, name: event.target.value }))}
              className="w-full rounded-xl border border-[rgb(var(--border))] bg-[rgb(var(--bg-muted))] px-3 py-2"
            />
          </label>
          <label className="space-y-1">
            <span className="text-sm font-medium">Dosage</span>
            <input
              value={newMedicine.dosage}
              onChange={(event) => setNewMedicine((prev) => ({ ...prev, dosage: event.target.value }))}
              className="w-full rounded-xl border border-[rgb(var(--border))] bg-[rgb(var(--bg-muted))] px-3 py-2"
            />
          </label>
          <label className="space-y-1">
            <span className="text-sm font-medium">Reminder time</span>
            <input
              value={newMedicine.reminder_times[0]}
              onChange={(event) =>
                setNewMedicine((prev) => ({ ...prev, reminder_times: [event.target.value || "08:00"] }))
              }
              className="w-full rounded-xl border border-[rgb(var(--border))] bg-[rgb(var(--bg-muted))] px-3 py-2"
            />
          </label>
          <label className="space-y-1">
            <span className="text-sm font-medium">Times per day</span>
            <input
              type="number"
              min={1}
              max={12}
              value={newMedicine.times_per_day}
              onChange={(event) => setNewMedicine((prev) => ({ ...prev, times_per_day: Number(event.target.value) }))}
              className="w-full rounded-xl border border-[rgb(var(--border))] bg-[rgb(var(--bg-muted))] px-3 py-2"
            />
          </label>
        </div>
      </Modal>
    </div>
  );
}
