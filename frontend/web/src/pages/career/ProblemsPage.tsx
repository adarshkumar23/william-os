import clsx from "clsx";
import { Plus, Flame } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import ProgressRing from "../../components/ui/ProgressRing";
import { api } from "../../services/api";

type Problem = {
  id: string;
  platform: string | null;
  title: string;
  difficulty: string | null;
  topics: string[];
  url: string | null;
  solved_at: string | null;
  time_spent_minutes: number | null;
  notes: string | null;
};

const DIFFICULTY_COLORS: Record<string, string> = {
  easy: "bg-green-500/15 text-green-300",
  medium: "bg-amber-500/15 text-amber-300",
  hard: "bg-red-500/15 text-red-300",
};

function AddProblemModal({ onClose, onAdd }: { onClose: () => void; onAdd: (p: Problem) => void }) {
  const [form, setForm] = useState({
    title: "", platform: "", difficulty: "medium",
    topics: "", url: "", solved_at: "", time_spent_minutes: "", notes: "",
  });
  const [saving, setSaving] = useState(false);

  const submit = async () => {
    if (!form.title) return;
    setSaving(true);
    try {
      const result = await api.career.createProblem({
        title: form.title,
        platform: form.platform || null,
        difficulty: form.difficulty || null,
        topics: form.topics ? form.topics.split(",").map((t) => t.trim()).filter(Boolean) : [],
        url: form.url || null,
        solved_at: form.solved_at ? new Date(form.solved_at).toISOString() : null,
        time_spent_minutes: form.time_spent_minutes ? parseInt(form.time_spent_minutes) : null,
        notes: form.notes || null,
      });
      onAdd(result as Problem);
      onClose();
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="w-[480px] rounded-xl border border-border bg-surface p-6 shadow-2xl">
        <h3 className="mb-4 font-semibold text-text-primary">Add Problem</h3>
        <div className="grid grid-cols-2 gap-3">
          {[
            { key: "title", label: "Title", col: 2, placeholder: "Two Sum" },
            { key: "platform", label: "Platform", col: 1, placeholder: "leetcode" },
            { key: "difficulty", label: "Difficulty", col: 1, placeholder: "medium" },
            { key: "topics", label: "Topics (comma-separated)", col: 2, placeholder: "array, hashmap" },
            { key: "url", label: "URL", col: 2, placeholder: "https://leetcode.com/..." },
            { key: "solved_at", label: "Solved At", col: 1, placeholder: "" },
            { key: "time_spent_minutes", label: "Time (min)", col: 1, placeholder: "30" },
            { key: "notes", label: "Notes", col: 2, placeholder: "Used two-pointer approach..." },
          ].map(({ key, label, col, placeholder }) => (
            <div key={key} className={col === 2 ? "col-span-2" : ""}>
              <label className="mb-1 block text-xs text-text-secondary">{label}</label>
              <input
                type={key === "solved_at" ? "date" : "text"}
                className="w-full rounded-lg border border-border bg-surface-raised px-3 py-2 text-sm text-text-primary placeholder-text-secondary focus:border-indigo-400 focus:outline-none"
                placeholder={placeholder}
                value={(form as Record<string, string>)[key]}
                onChange={(e) => setForm((f) => ({ ...f, [key]: e.target.value }))}
              />
            </div>
          ))}
        </div>
        <div className="mt-4 flex gap-2">
          <button className="flex-1 rounded-lg border border-border px-4 py-2 text-sm text-text-secondary hover:bg-surface-raised" onClick={onClose}>Cancel</button>
          <button className="flex-1 rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-500 disabled:opacity-50" onClick={submit} disabled={saving || !form.title}>
            {saving ? "Adding..." : "Add"}
          </button>
        </div>
      </div>
    </div>
  );
}

export default function ProblemsPage() {
  const [problems, setProblems] = useState<Problem[]>([]);
  const [loading, setLoading] = useState(true);
  const [showModal, setShowModal] = useState(false);
  const [filterPlatform, setFilterPlatform] = useState("");
  const [filterDifficulty, setFilterDifficulty] = useState("");

  const load = useCallback(async () => {
    try {
      const result = await api.career.listProblems({
        platform: filterPlatform || undefined,
        difficulty: filterDifficulty || undefined,
      });
      setProblems(result as Problem[]);
    } finally {
      setLoading(false);
    }
  }, [filterPlatform, filterDifficulty]);

  useEffect(() => { void load(); }, [load]);

  const solved = problems.filter((p) => p.solved_at).length;
  const streak = Math.min(solved, 30);

  const platforms = Array.from(new Set(problems.map((p) => p.platform).filter(Boolean)));

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-text-primary">Problems</h1>
          <p className="meta-copy mt-1">{solved} solved</p>
        </div>
        <button onClick={() => setShowModal(true)} className="flex items-center gap-2 rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-500">
          <Plus className="h-4 w-4" /> Add Problem
        </button>
      </div>

      {/* Stats row */}
      <div className="flex items-start gap-6 rounded-xl border border-border bg-surface p-4">
        <ProgressRing value={(solved / 400) * 100} size="md" color="rgb(99,102,241)" label="DSA Score" sublabel={`${solved}/400`} />
        <div className="flex items-center gap-2">
          <Flame className="h-5 w-5 text-orange-400" />
          <div>
            <p className="text-2xl font-bold text-text-primary">{streak}</p>
            <p className="meta-copy">Streak</p>
          </div>
        </div>
        <div className="flex gap-3">
          {["easy", "medium", "hard"].map((d) => {
            const count = problems.filter((p) => p.difficulty === d).length;
            return (
              <div key={d} className="text-center">
                <p className="text-xl font-bold text-text-primary">{count}</p>
                <span className={clsx("rounded-full px-2 py-0.5 text-xs capitalize", DIFFICULTY_COLORS[d])}>{d}</span>
              </div>
            );
          })}
        </div>
      </div>

      {/* Filters */}
      <div className="flex gap-3">
        <select className="rounded-lg border border-border bg-surface px-3 py-2 text-sm text-text-primary focus:outline-none" value={filterPlatform} onChange={(e) => setFilterPlatform(e.target.value)}>
          <option value="">All Platforms</option>
          {platforms.map((p) => <option key={p} value={p!}>{p}</option>)}
        </select>
        <select className="rounded-lg border border-border bg-surface px-3 py-2 text-sm text-text-primary focus:outline-none" value={filterDifficulty} onChange={(e) => setFilterDifficulty(e.target.value)}>
          <option value="">All Difficulties</option>
          {["easy", "medium", "hard"].map((d) => <option key={d} value={d}>{d}</option>)}
        </select>
      </div>

      {/* Table */}
      {loading ? (
        <div className="flex h-32 items-center justify-center">
          <div className="h-6 w-6 animate-spin rounded-full border-2 border-indigo-500 border-t-transparent" />
        </div>
      ) : (
        <div className="rounded-xl border border-border bg-surface overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border text-left">
                <th className="px-4 py-3 text-xs font-medium text-text-secondary">Title</th>
                <th className="px-4 py-3 text-xs font-medium text-text-secondary">Platform</th>
                <th className="px-4 py-3 text-xs font-medium text-text-secondary">Difficulty</th>
                <th className="px-4 py-3 text-xs font-medium text-text-secondary">Topics</th>
                <th className="px-4 py-3 text-xs font-medium text-text-secondary">Solved</th>
              </tr>
            </thead>
            <tbody>
              {problems.length === 0 ? (
                <tr><td colSpan={5} className="py-8 text-center text-text-secondary">No problems yet</td></tr>
              ) : problems.map((p) => (
                <tr key={p.id} className="border-b border-border/50 hover:bg-surface-raised">
                  <td className="px-4 py-3">
                    {p.url ? (
                      <a href={p.url} target="_blank" rel="noopener noreferrer" className="text-text-primary hover:text-indigo-300">{p.title}</a>
                    ) : (
                      <span className="text-text-primary">{p.title}</span>
                    )}
                  </td>
                  <td className="px-4 py-3 text-text-secondary capitalize">{p.platform || "—"}</td>
                  <td className="px-4 py-3">
                    {p.difficulty && <span className={clsx("rounded-full px-2 py-0.5 text-xs capitalize", DIFFICULTY_COLORS[p.difficulty] ?? "")}>{p.difficulty}</span>}
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex flex-wrap gap-1">
                      {p.topics.slice(0, 3).map((t) => <span key={t} className="rounded-full bg-surface-raised px-2 py-0.5 text-[10px] text-text-secondary">{t}</span>)}
                    </div>
                  </td>
                  <td className="px-4 py-3 text-text-secondary">{p.solved_at ? new Date(p.solved_at).toLocaleDateString() : "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {showModal && <AddProblemModal onClose={() => setShowModal(false)} onAdd={(p) => setProblems((prev) => [p, ...prev])} />}
    </div>
  );
}
