import { Pill, SkipForward } from "lucide-react";

import { Medicine } from "../types/api";

type MedicineCardProps = {
  medicine: Medicine;
  nextDue?: string;
  onTake: (medicine: Medicine) => Promise<void>;
  onSkip: (medicine: Medicine, reason: string) => Promise<void>;
};

export default function MedicineCard({ medicine, nextDue, onTake, onSkip }: MedicineCardProps) {
  return (
    <article className="card p-4">
      <div className="mb-3 flex items-start justify-between gap-3">
        <div>
          <h3 className="text-lg font-semibold">{medicine.name}</h3>
          <p className="text-sm text-[rgb(var(--text-dim))]">{medicine.dosage}</p>
          <p className="mt-1 data-font text-xs text-[rgb(var(--warning))]">Next: {nextDue || "Not scheduled"}</p>
        </div>
        <Pill className="h-5 w-5 text-[rgb(var(--primary))]" />
      </div>
      <div className="flex items-center gap-2">
        <button
          type="button"
          onClick={() => void onTake(medicine)}
          className="rounded-lg bg-[rgb(var(--success))] px-3 py-1.5 text-xs font-semibold text-slate-900"
        >
          Take
        </button>
        <button
          type="button"
          onClick={() => {
            const reason = window.prompt("Skip reason") || "Skipped from dashboard";
            void onSkip(medicine, reason);
          }}
          className="inline-flex items-center gap-1 rounded-lg border border-[rgb(var(--danger))]/40 px-3 py-1.5 text-xs font-semibold text-[rgb(var(--danger))]"
        >
          <SkipForward className="h-3.5 w-3.5" /> Skip
        </button>
      </div>
    </article>
  );
}
