import clsx from "clsx";
import { Plus, X } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { api } from "../../services/api";

type Opportunity = {
  id: string;
  title: string;
  source: string | null;
  kind: string;
  url: string | null;
  description: string | null;
  deadline: string | null;
  stipend_info: string | null;
  status: string;
  converted_to_application_id: string | null;
};

const KIND_COLORS: Record<string, string> = {
  hackathon: "bg-purple-500/15 text-purple-300",
  oss: "bg-green-500/15 text-green-300",
  internship: "bg-blue-500/15 text-blue-300",
  cert: "bg-amber-500/15 text-amber-300",
  other: "bg-zinc-500/15 text-zinc-300",
};

const TABS = ["inbox", "tracking", "ignored", "converted"] as const;

function CountdownChip({ deadline }: { deadline: string | null }) {
  if (!deadline) return <span className="text-xs text-text-secondary">No deadline</span>;
  const d = new Date(deadline);
  const daysLeft = Math.ceil((d.getTime() - Date.now()) / 86400000);
  const cls =
    daysLeft > 7 ? "text-green-400"
    : daysLeft > 3 ? "text-amber-400"
    : daysLeft > 0 ? "text-red-400"
    : "text-text-secondary line-through";
  return <span className={clsx("text-xs", cls)}>{daysLeft > 0 ? `${daysLeft}d left` : "Overdue"}</span>;
}

function ConvertModal({ opp, onClose, onConverted }: { opp: Opportunity; onClose: () => void; onConverted: (id: string) => void }) {
  const [form, setForm] = useState({ role: opp.title, platform: "" });
  const [saving, setSaving] = useState(false);

  const submit = async () => {
    setSaving(true);
    try {
      await api.career.convertOpportunity(opp.id, { role: form.role, platform: form.platform || undefined });
      onConverted(opp.id);
      onClose();
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="w-96 rounded-xl border border-border bg-surface p-6 shadow-2xl">
        <div className="mb-4 flex items-center justify-between">
          <h3 className="font-semibold text-text-primary">Add to Applications</h3>
          <button onClick={onClose}><X className="h-4 w-4 text-text-secondary" /></button>
        </div>
        <div className="space-y-3">
          <div>
            <label className="mb-1 block text-xs text-text-secondary">Role</label>
            <input className="w-full rounded-lg border border-border bg-surface-raised px-3 py-2 text-sm text-text-primary focus:border-indigo-400 focus:outline-none" value={form.role} onChange={(e) => setForm((f) => ({ ...f, role: e.target.value }))} />
          </div>
          <div>
            <label className="mb-1 block text-xs text-text-secondary">Platform</label>
            <input className="w-full rounded-lg border border-border bg-surface-raised px-3 py-2 text-sm text-text-primary placeholder-text-secondary focus:border-indigo-400 focus:outline-none" placeholder="devfolio, unstop..." value={form.platform} onChange={(e) => setForm((f) => ({ ...f, platform: e.target.value }))} />
          </div>
        </div>
        <div className="mt-4 flex gap-2">
          <button className="flex-1 rounded-lg border border-border px-4 py-2 text-sm text-text-secondary hover:bg-surface-raised" onClick={onClose}>Cancel</button>
          <button className="flex-1 rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-500 disabled:opacity-50" onClick={submit} disabled={saving || !form.role}>{saving ? "Converting..." : "Convert"}</button>
        </div>
      </div>
    </div>
  );
}

function AddOpportunityModal({ onClose, onAdd }: { onClose: () => void; onAdd: (o: Opportunity) => void }) {
  const [form, setForm] = useState({ title: "", source: "", kind: "other", url: "", description: "", deadline: "", stipend_info: "" });
  const [saving, setSaving] = useState(false);

  const submit = async () => {
    if (!form.title) return;
    setSaving(true);
    try {
      const result = await api.career.createOpportunity({ title: form.title, source: form.source || null, kind: form.kind, url: form.url || null, description: form.description || null, deadline: form.deadline ? new Date(form.deadline).toISOString() : null, stipend_info: form.stipend_info || null });
      onAdd(result as Opportunity);
      onClose();
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="w-[480px] rounded-xl border border-border bg-surface p-6 shadow-2xl">
        <h3 className="mb-4 font-semibold text-text-primary">Add Opportunity</h3>
        <div className="grid grid-cols-2 gap-3">
          {[
            { key: "title", label: "Title", col: 2, placeholder: "Google Summer of Code" },
            { key: "source", label: "Source", col: 1, placeholder: "Twitter" },
            { key: "stipend_info", label: "Stipend", col: 1, placeholder: "$3000/month" },
            { key: "url", label: "URL", col: 2, placeholder: "https://..." },
            { key: "description", label: "Description", col: 2, placeholder: "Brief description..." },
            { key: "deadline", label: "Deadline", col: 1, placeholder: "" },
          ].map(({ key, label, col, placeholder }) => (
            <div key={key} className={col === 2 ? "col-span-2" : ""}>
              <label className="mb-1 block text-xs text-text-secondary">{label}</label>
              <input type={key === "deadline" ? "date" : "text"} className="w-full rounded-lg border border-border bg-surface-raised px-3 py-2 text-sm text-text-primary placeholder-text-secondary focus:border-indigo-400 focus:outline-none" placeholder={placeholder} value={(form as Record<string, string>)[key]} onChange={(e) => setForm((f) => ({ ...f, [key]: e.target.value }))} />
            </div>
          ))}
          <div>
            <label className="mb-1 block text-xs text-text-secondary">Kind</label>
            <select className="w-full rounded-lg border border-border bg-surface-raised px-3 py-2 text-sm text-text-primary focus:outline-none" value={form.kind} onChange={(e) => setForm((f) => ({ ...f, kind: e.target.value }))}>
              {["hackathon", "oss", "internship", "cert", "other"].map((k) => <option key={k} value={k}>{k}</option>)}
            </select>
          </div>
        </div>
        <div className="mt-4 flex gap-2">
          <button className="flex-1 rounded-lg border border-border px-4 py-2 text-sm text-text-secondary hover:bg-surface-raised" onClick={onClose}>Cancel</button>
          <button className="flex-1 rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-500 disabled:opacity-50" onClick={submit} disabled={saving || !form.title}>{saving ? "Adding..." : "Add"}</button>
        </div>
      </div>
    </div>
  );
}

export default function OpportunitiesPage() {
  const [opps, setOpps] = useState<Opportunity[]>([]);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<typeof TABS[number]>("inbox");
  const [showModal, setShowModal] = useState(false);
  const [convertOpp, setConvertOpp] = useState<Opportunity | null>(null);

  const load = useCallback(async () => {
    try {
      const result = await api.career.listOpportunities();
      setOpps(result as Opportunity[]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { void load(); }, [load]);

  const tabOpps = opps.filter((o) => o.status === activeTab).sort((a, b) => {
    if (!a.deadline) return 1;
    if (!b.deadline) return -1;
    return new Date(a.deadline).getTime() - new Date(b.deadline).getTime();
  });

  const ignore = async (id: string) => {
    await api.career.updateOpportunity(id, { status: "ignored" });
    setOpps((prev) => prev.map((o) => o.id === id ? { ...o, status: "ignored" } : o));
  };

  const counts = Object.fromEntries(TABS.map((t) => [t, opps.filter((o) => o.status === t).length]));

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-text-primary">Opportunities</h1>
          <p className="meta-copy mt-1">{counts["inbox"]} in inbox</p>
        </div>
        <button onClick={() => setShowModal(true)} className="flex items-center gap-2 rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-500">
          <Plus className="h-4 w-4" /> Add Opportunity
        </button>
      </div>

      <div className="flex gap-2 border-b border-border pb-3">
        {TABS.map((tab) => (
          <button key={tab} onClick={() => setActiveTab(tab)} className={clsx("rounded-lg px-3 py-1.5 text-sm capitalize transition", activeTab === tab ? "bg-indigo-500/20 text-indigo-300" : "text-text-secondary hover:bg-surface-raised")}>
            {tab}
            {counts[tab] > 0 && <span className="ml-1.5 rounded-full bg-surface-raised px-1.5 py-0.5 text-[10px]">{counts[tab]}</span>}
          </button>
        ))}
      </div>

      {loading ? (
        <div className="flex h-32 items-center justify-center"><div className="h-6 w-6 animate-spin rounded-full border-2 border-indigo-500 border-t-transparent" /></div>
      ) : tabOpps.length === 0 ? (
        <p className="py-8 text-center text-text-secondary">No {activeTab} opportunities</p>
      ) : (
        <div className="space-y-2">
          {tabOpps.map((opp) => (
            <div key={opp.id} className="flex items-center gap-4 rounded-xl border border-border bg-surface px-4 py-3">
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2">
                  <p className="font-medium text-text-primary truncate">{opp.title}</p>
                  <span className={clsx("shrink-0 rounded-full px-2 py-0.5 text-[10px] capitalize", KIND_COLORS[opp.kind] ?? "")}>{opp.kind}</span>
                  {opp.source && <span className="shrink-0 rounded-full bg-surface-raised px-2 py-0.5 text-[10px] text-text-secondary">{opp.source}</span>}
                </div>
                {opp.stipend_info && <p className="mt-0.5 text-xs text-green-400">{opp.stipend_info}</p>}
              </div>
              <CountdownChip deadline={opp.deadline} />
              {activeTab === "inbox" && (
                <div className="flex shrink-0 gap-2">
                  <button onClick={() => setConvertOpp(opp)} className="rounded-lg bg-indigo-500/15 px-3 py-1.5 text-xs text-indigo-300 hover:bg-indigo-500/25">
                    Add to Apps
                  </button>
                  <button onClick={() => ignore(opp.id)} className="rounded-lg bg-surface-raised px-3 py-1.5 text-xs text-text-secondary hover:text-text-primary">
                    Ignore
                  </button>
                </div>
              )}
              {opp.url && (
                <a href={opp.url} target="_blank" rel="noopener noreferrer" className="shrink-0 text-xs text-indigo-400 hover:text-indigo-300">
                  Link →
                </a>
              )}
            </div>
          ))}
        </div>
      )}

      {showModal && <AddOpportunityModal onClose={() => setShowModal(false)} onAdd={(o) => setOpps((prev) => [o, ...prev])} />}
      {convertOpp && <ConvertModal opp={convertOpp} onClose={() => setConvertOpp(null)} onConverted={(id) => setOpps((prev) => prev.map((o) => o.id === id ? { ...o, status: "converted" } : o))} />}
    </div>
  );
}
