type Medicine = {
  id: string;
  name: string;
  dosage: string;
  remaining_count?: number | null;
  reminder_times: string[];
};

export default function MedicineCard({
  medicine,
  onTake,
  onSkip,
}: {
  medicine: Medicine;
  onTake: () => void;
  onSkip: () => void;
}) {
  return (
    <article className="panel p-4 animate-rise">
      <h3 className="font-display text-lg font-bold">{medicine.name}</h3>
      <p className="text-sm text-slate-500 dark:text-slate-400">{medicine.dosage}</p>
      <p className="mt-2 text-sm">
        Next reminders: {medicine.reminder_times?.join(", ") || "N/A"}
      </p>
      <p className="mt-1 text-sm">Remaining: {medicine.remaining_count ?? "Unknown"}</p>
      <div className="mt-4 grid grid-cols-2 gap-2">
        <button className="btn-primary" onClick={onTake} type="button">
          Take
        </button>
        <button className="btn-secondary" onClick={onSkip} type="button">
          Skip
        </button>
      </div>
    </article>
  );
}
