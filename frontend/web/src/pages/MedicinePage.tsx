import { motion, useReducedMotion } from "framer-motion";
import { Plus, Pill, TriangleAlert } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { Bar, BarChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { fadeInUp, reduceMotion, staggerContainer } from "../lib/animations";
import { api } from "../services/api";
import { Medicine, MedicineReminder } from "../types/api";
import { AppCard, EmptyState, ProgressRing, SectionHeader, SkeletonLoader } from "../components/ui";

export default function MedicinePage() {
  const [medicines, setMedicines] = useState<Medicine[]>([]);
  const [reminders, setReminders] = useState<MedicineReminder[]>([]);
  const [adherence, setAdherence] = useState<{ total_taken: number; total_skipped: number; adherence_rate: number } | null>(
    null,
  );
  const [refills, setRefills] = useState<Medicine[]>([]);
  const [loading, setLoading] = useState(true);
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

  const shouldReduceMotion = useReducedMotion();
  const fadeMotion = reduceMotion(shouldReduceMotion, fadeInUp);

  const load = async () => {
    setLoading(true);
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
    setLoading(false);
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

  const chartData = useMemo(
    () => [
      { name: "Taken", value: adherence?.total_taken ?? 0 },
      { name: "Skipped", value: adherence?.total_skipped ?? 0 },
    ],
    [adherence?.total_skipped, adherence?.total_taken],
  );

  const ringColor =
    (adherence?.adherence_rate || 0) >= 85
      ? "rgb(var(--color-success))"
      : (adherence?.adherence_rate || 0) >= 65
        ? "rgb(var(--color-warning))"
        : "rgb(var(--color-danger))";

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
      <SectionHeader
        title="Medicine"
        subtitle="Calm daily adherence with reliable reminders and refill awareness."
        action={
          <button
            type="button"
            onClick={() => setOpenAdd(true)}
            className="inline-flex items-center gap-2 rounded-button bg-accent px-4 py-2 text-sm font-semibold text-white"
          >
            <Plus className="h-4 w-4" /> Add Medicine
          </button>
        }
      />

      <motion.section variants={staggerContainer} initial="initial" animate="animate" className="grid gap-4 lg:grid-cols-3">
        <motion.div variants={fadeMotion}>
          <AppCard hover className="h-full">
            <p className="section-label">Adherence</p>
            <div className="mt-3">
              <ProgressRing
                value={Math.round(adherence?.adherence_rate || 0)}
                color={ringColor}
                label="30 Day"
                sublabel="taken vs skipped"
              />
            </div>
          </AppCard>
        </motion.div>

        <motion.div variants={fadeMotion} className="lg:col-span-2">
          <AppCard>
            <p className="section-label">Adherence Trend</p>
            <div className="mt-4 h-56">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={chartData}>
                  <XAxis dataKey="name" stroke="rgb(var(--color-text-muted))" tick={{ fontSize: 11 }} />
                  <YAxis stroke="rgb(var(--color-text-muted))" tick={{ fontSize: 11 }} />
                  <Tooltip />
                  <Bar dataKey="value" fill="rgb(var(--color-success))" radius={[8, 8, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </AppCard>
        </motion.div>
      </motion.section>

      {refills.length > 0 ? (
        <div className="space-y-2">
          {refills.map((medicine) => (
            <div key={medicine.id} className="rounded-xl border border-warning/40 bg-warning/10 px-3 py-2 text-sm text-warning">
              <TriangleAlert className="mr-1 inline h-4 w-4" /> Refill alert for {medicine.name}
            </div>
          ))}
        </div>
      ) : null}

      {loading ? (
        <div className="space-y-2">
          {Array.from({ length: 3 }).map((_, idx) => (
            <SkeletonLoader key={idx} variant="card" />
          ))}
        </div>
      ) : medicines.length === 0 ? (
        <EmptyState
          icon={<Pill className="h-6 w-6" />}
          title="No medicines added"
          description="Add your routine medicines to start adherence tracking and reminders."
          action={
            <button
              type="button"
              onClick={() => setOpenAdd(true)}
              className="rounded-button bg-accent px-4 py-2 text-sm font-semibold text-white"
            >
              Add Medicine
            </button>
          }
        />
      ) : (
        <AppCard>
          <p className="section-label">Upcoming Doses</p>
          <div className="mt-4 space-y-2">
            {medicines.map((medicine) => {
              const nextDue = reminders.find((item) => item.medicine_name === medicine.name)?.scheduled_time || "Not scheduled";
              return (
                <div key={medicine.id} className="flex items-center justify-between gap-3 rounded-lg border border-border bg-surface-raised p-3">
                  <div>
                    <p className="text-sm font-medium text-text-primary">{medicine.name}</p>
                    <p className="meta-copy">{medicine.dosage} • {nextDue}</p>
                  </div>
                  <div className="flex gap-2">
                    <button
                      type="button"
                      onClick={() => void onTake(medicine)}
                      className="rounded-button bg-success/15 px-3 py-1.5 text-xs font-medium text-success"
                    >
                      Take
                    </button>
                    <button
                      type="button"
                      onClick={() => {
                        const reason = window.prompt("Skip reason") || "Skipped";
                        void onSkip(medicine, reason);
                      }}
                      className="rounded-button border border-danger/40 px-3 py-1.5 text-xs font-medium text-danger"
                    >
                      Skip
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        </AppCard>
      )}

      {openAdd ? (
        <AppCard>
          <p className="section-label">Add Medicine</p>
          <div className="mt-3 grid gap-3 md:grid-cols-2">
            <input
              value={newMedicine.name}
              onChange={(event) => setNewMedicine((prev) => ({ ...prev, name: event.target.value }))}
              placeholder="Name"
              className="rounded-input border border-border bg-surface-raised px-3 py-2 text-sm"
            />
            <input
              value={newMedicine.dosage}
              onChange={(event) => setNewMedicine((prev) => ({ ...prev, dosage: event.target.value }))}
              placeholder="Dosage"
              className="rounded-input border border-border bg-surface-raised px-3 py-2 text-sm"
            />
            <input
              value={newMedicine.reminder_times[0]}
              onChange={(event) => setNewMedicine((prev) => ({ ...prev, reminder_times: [event.target.value || "08:00"] }))}
              placeholder="Reminder time"
              className="rounded-input border border-border bg-surface-raised px-3 py-2 text-sm"
            />
            <input
              type="number"
              min={1}
              max={12}
              value={newMedicine.times_per_day}
              onChange={(event) => setNewMedicine((prev) => ({ ...prev, times_per_day: Number(event.target.value) }))}
              placeholder="Times per day"
              className="rounded-input border border-border bg-surface-raised px-3 py-2 text-sm"
            />
          </div>
          <div className="mt-3 flex justify-end gap-2">
            <button type="button" className="rounded-button border border-border px-4 py-2 text-sm" onClick={() => setOpenAdd(false)}>
              Cancel
            </button>
            <button type="button" className="rounded-button bg-accent px-4 py-2 text-sm font-semibold text-white" onClick={() => void onCreate()}>
              Save
            </button>
          </div>
        </AppCard>
      ) : null}
    </div>
  );
}
