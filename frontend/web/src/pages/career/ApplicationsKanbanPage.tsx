import {
  DndContext,
  DragEndEvent,
  DragOverlay,
  DragStartEvent,
  PointerSensor,
  useSensor,
  useSensors,
} from "@dnd-kit/core";
import { SortableContext, useSortable, verticalListSortingStrategy } from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import clsx from "clsx";
import { ChevronDown, ChevronUp, MoreHorizontal, Plus } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "../../services/api";

type Application = {
  id: string;
  company: string;
  role: string;
  platform: string | null;
  stage: string;
  next_action: string | null;
  next_action_due: string | null;
  archived: boolean;
};

type Pipeline = Record<string, Application[]>;

const STAGES = ["researching", "applied", "oa", "interview", "offer", "rejected"] as const;

const STAGE_LABELS: Record<string, string> = {
  researching: "Researching",
  applied: "Applied",
  oa: "OA",
  interview: "Interview",
  offer: "Offer",
  rejected: "Rejected",
};

const STAGE_COLORS: Record<string, string> = {
  researching: "bg-zinc-500/15 text-zinc-300",
  applied: "bg-blue-500/15 text-blue-300",
  oa: "bg-purple-500/15 text-purple-300",
  interview: "bg-amber-500/15 text-amber-300",
  offer: "bg-green-500/15 text-green-300",
  rejected: "bg-red-500/15 text-red-300",
};

function ApplicationCard({ app, onDelete, onArchive }: { app: Application; onDelete: (id: string) => void; onArchive: (id: string) => void }) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({ id: app.id });
  const [menuOpen, setMenuOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setMenuOpen(false);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  const dueDate = app.next_action_due ? new Date(app.next_action_due) : null;
  const isOverdue = dueDate && dueDate < new Date();

  return (
    <div
      ref={setNodeRef}
      style={{ transform: CSS.Transform.toString(transform), transition }}
      className={clsx(
        "rounded-lg border border-border bg-surface-raised p-3 cursor-grab active:cursor-grabbing select-none",
        isDragging && "opacity-50",
      )}
      {...attributes}
      {...listeners}
    >
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="truncate font-medium text-text-primary text-sm">{app.company}</p>
          <p className="truncate text-xs text-text-secondary">{app.role}</p>
        </div>
        <div className="relative shrink-0" ref={menuRef}>
          <button
            onClick={(e) => { e.stopPropagation(); setMenuOpen((v) => !v); }}
            className="rounded p-0.5 text-text-secondary hover:bg-surface hover:text-text-primary"
            onPointerDown={(e) => e.stopPropagation()}
          >
            <MoreHorizontal className="h-4 w-4" />
          </button>
          {menuOpen && (
            <div className="absolute right-0 top-6 z-10 min-w-[120px] rounded-lg border border-border bg-surface shadow-lg">
              <button
                className="w-full px-3 py-2 text-left text-xs text-text-secondary hover:bg-surface-raised hover:text-text-primary"
                onPointerDown={(e) => e.stopPropagation()}
                onClick={() => { onArchive(app.id); setMenuOpen(false); }}
              >
                Archive
              </button>
              <button
                className="w-full px-3 py-2 text-left text-xs text-red-400 hover:bg-surface-raised"
                onPointerDown={(e) => e.stopPropagation()}
                onClick={() => { onDelete(app.id); setMenuOpen(false); }}
              >
                Delete
              </button>
            </div>
          )}
        </div>
      </div>
      {app.platform && (
        <span className="mt-1.5 inline-block rounded-full bg-surface px-2 py-0.5 text-[10px] text-text-secondary">
          {app.platform}
        </span>
      )}
      {app.next_action && (
        <p className={clsx("mt-1.5 text-[11px]", isOverdue ? "text-red-400" : "text-text-secondary")}>
          {app.next_action}
          {dueDate && ` · ${dueDate.toLocaleDateString()}`}
        </p>
      )}
    </div>
  );
}

function AddApplicationModal({ onClose, onAdd }: { onClose: () => void; onAdd: (app: Application) => void }) {
  const [form, setForm] = useState({ company: "", role: "", platform: "", stage: "researching" });
  const [saving, setSaving] = useState(false);

  const submit = async () => {
    if (!form.company || !form.role) return;
    setSaving(true);
    try {
      const result = await api.career.createApplication({
        company: form.company,
        role: form.role,
        platform: form.platform || null,
        stage: form.stage,
      });
      onAdd(result as Application);
      onClose();
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="w-96 rounded-xl border border-border bg-surface p-6 shadow-2xl">
        <h3 className="mb-4 font-semibold text-text-primary">Add Application</h3>
        <div className="space-y-3">
          {[
            { key: "company", label: "Company", placeholder: "Razorpay" },
            { key: "role", label: "Role", placeholder: "SDE Intern" },
            { key: "platform", label: "Platform", placeholder: "LinkedIn" },
          ].map(({ key, label, placeholder }) => (
            <div key={key}>
              <label className="mb-1 block text-xs text-text-secondary">{label}</label>
              <input
                className="w-full rounded-lg border border-border bg-surface-raised px-3 py-2 text-sm text-text-primary placeholder-text-secondary focus:border-indigo-400 focus:outline-none"
                placeholder={placeholder}
                value={(form as Record<string, string>)[key]}
                onChange={(e) => setForm((f) => ({ ...f, [key]: e.target.value }))}
              />
            </div>
          ))}
          <div>
            <label className="mb-1 block text-xs text-text-secondary">Stage</label>
            <select
              className="w-full rounded-lg border border-border bg-surface-raised px-3 py-2 text-sm text-text-primary focus:outline-none"
              value={form.stage}
              onChange={(e) => setForm((f) => ({ ...f, stage: e.target.value }))}
            >
              {STAGES.map((s) => <option key={s} value={s}>{STAGE_LABELS[s]}</option>)}
            </select>
          </div>
        </div>
        <div className="mt-4 flex gap-2">
          <button
            className="flex-1 rounded-lg border border-border px-4 py-2 text-sm text-text-secondary hover:bg-surface-raised"
            onClick={onClose}
          >
            Cancel
          </button>
          <button
            className="flex-1 rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-500 disabled:opacity-50"
            onClick={submit}
            disabled={saving || !form.company || !form.role}
          >
            {saving ? "Adding..." : "Add"}
          </button>
        </div>
      </div>
    </div>
  );
}

export default function ApplicationsKanbanPage() {
  const [pipeline, setPipeline] = useState<Pipeline>({});
  const [loading, setLoading] = useState(true);
  const [activeApp, setActiveApp] = useState<Application | null>(null);
  const [rejectedOpen, setRejectedOpen] = useState(false);
  const [showAddModal, setShowAddModal] = useState(false);
  const [toast, setToast] = useState<string | null>(null);

  const sensors = useSensors(useSensor(PointerSensor, { activationConstraint: { distance: 8 } }));

  const load = useCallback(async () => {
    try {
      const result = await api.career.getApplicationPipeline();
      setPipeline(result as Pipeline);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { void load(); }, [load]);

  const showToast = (msg: string) => {
    setToast(msg);
    setTimeout(() => setToast(null), 3000);
  };

  const handleDragStart = (event: DragStartEvent) => {
    const appId = String(event.active.id);
    for (const apps of Object.values(pipeline)) {
      const found = apps.find((a) => a.id === appId);
      if (found) { setActiveApp(found); break; }
    }
  };

  const handleDragEnd = async (event: DragEndEvent) => {
    setActiveApp(null);
    const { active, over } = event;
    if (!over) return;

    const appId = String(active.id);
    const newStage = String(over.id);
    if (!STAGES.includes(newStage as typeof STAGES[number])) return;

    let oldStage = "";
    for (const [stage, apps] of Object.entries(pipeline)) {
      if (apps.some((a) => a.id === appId)) { oldStage = stage; break; }
    }
    if (!oldStage || oldStage === newStage) return;

    // Optimistic update
    const app = pipeline[oldStage].find((a) => a.id === appId)!;
    const updated = { ...app, stage: newStage };
    setPipeline((prev) => {
      const next = { ...prev };
      next[oldStage] = next[oldStage].filter((a) => a.id !== appId);
      next[newStage] = [updated, ...(next[newStage] ?? [])];
      return next;
    });

    try {
      await api.career.updateApplicationStage(appId, newStage);
    } catch {
      // Rollback
      setPipeline((prev) => {
        const next = { ...prev };
        next[newStage] = next[newStage].filter((a) => a.id !== appId);
        next[oldStage] = [app, ...(next[oldStage] ?? [])];
        return next;
      });
      showToast("Failed to move application — reverted");
    }
  };

  const handleDelete = async (appId: string) => {
    await api.career.deleteApplication(appId);
    setPipeline((prev) => {
      const next = { ...prev };
      for (const stage of STAGES) {
        if (next[stage]) next[stage] = next[stage].filter((a) => a.id !== appId);
      }
      return next;
    });
  };

  const handleArchive = async (appId: string) => {
    await api.career.updateApplication(appId, { archived: true });
    setPipeline((prev) => {
      const next = { ...prev };
      for (const stage of STAGES) {
        if (next[stage]) next[stage] = next[stage].filter((a) => a.id !== appId);
      }
      return next;
    });
  };

  const handleAdd = (app: Application) => {
    setPipeline((prev) => ({
      ...prev,
      [app.stage]: [app, ...(prev[app.stage] ?? [])],
    }));
  };

  // Funnel counts
  const funnelStages = ["researching", "applied", "oa", "interview", "offer"] as const;
  const counts = funnelStages.map((s) => (pipeline[s] ?? []).length);

  if (loading) {
    return (
      <div className="flex h-64 items-center justify-center">
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-indigo-500 border-t-transparent" />
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-text-primary">Applications</h1>
          <p className="meta-copy mt-1">Drag cards to update stage.</p>
        </div>
        <button
          onClick={() => setShowAddModal(true)}
          className="flex items-center gap-2 rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-500"
        >
          <Plus className="h-4 w-4" /> Add Application
        </button>
      </div>

      {/* Funnel strip */}
      <div className="flex items-center gap-2 rounded-xl border border-border bg-surface px-4 py-3">
        {funnelStages.map((stage, i) => (
          <div key={stage} className="flex items-center gap-2">
            <div className="text-center">
              <span className="text-lg font-bold text-text-primary">{counts[i]}</span>
              <span className="ml-1 text-xs text-text-secondary capitalize">{STAGE_LABELS[stage]}</span>
            </div>
            {i < funnelStages.length - 1 && <span className="text-text-secondary">→</span>}
          </div>
        ))}
      </div>

      <DndContext sensors={sensors} onDragStart={handleDragStart} onDragEnd={handleDragEnd}>
        <div className="flex gap-3 overflow-x-auto pb-4">
          {STAGES.filter((s) => s !== "rejected").map((stage) => {
            const apps = pipeline[stage] ?? [];
            return (
              <SortableContext key={stage} id={stage} items={apps.map((a) => a.id)} strategy={verticalListSortingStrategy}>
                <div
                  id={stage}
                  className="flex w-60 shrink-0 flex-col gap-2 rounded-xl border border-border bg-surface p-3"
                >
                  <div className="flex items-center justify-between">
                    <span className={clsx("rounded-full px-2.5 py-0.5 text-xs font-semibold", STAGE_COLORS[stage])}>
                      {STAGE_LABELS[stage]}
                    </span>
                    <span className="text-xs text-text-secondary">{apps.length}</span>
                  </div>
                  <div className="space-y-2 min-h-[40px]">
                    {apps.map((app) => (
                      <ApplicationCard key={app.id} app={app} onDelete={handleDelete} onArchive={handleArchive} />
                    ))}
                  </div>
                </div>
              </SortableContext>
            );
          })}

          {/* Rejected column (collapsed) */}
          <div className="flex w-60 shrink-0 flex-col gap-2 rounded-xl border border-border bg-surface p-3">
            <button
              className="flex items-center justify-between"
              onClick={() => setRejectedOpen((v) => !v)}
            >
              <span className={clsx("rounded-full px-2.5 py-0.5 text-xs font-semibold", STAGE_COLORS["rejected"])}>
                Rejected
              </span>
              <div className="flex items-center gap-1 text-text-secondary">
                <span className="text-xs">{(pipeline["rejected"] ?? []).length}</span>
                {rejectedOpen ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />}
              </div>
            </button>
            {rejectedOpen && (
              <SortableContext id="rejected" items={(pipeline["rejected"] ?? []).map((a) => a.id)} strategy={verticalListSortingStrategy}>
                <div className="space-y-2">
                  {(pipeline["rejected"] ?? []).map((app) => (
                    <ApplicationCard key={app.id} app={app} onDelete={handleDelete} onArchive={handleArchive} />
                  ))}
                </div>
              </SortableContext>
            )}
          </div>
        </div>

        <DragOverlay>
          {activeApp && (
            <div className="w-60 rounded-lg border border-indigo-400/40 bg-surface-raised p-3 shadow-2xl opacity-90">
              <p className="font-medium text-text-primary text-sm">{activeApp.company}</p>
              <p className="text-xs text-text-secondary">{activeApp.role}</p>
            </div>
          )}
        </DragOverlay>
      </DndContext>

      {toast && (
        <div className="fixed bottom-6 left-1/2 -translate-x-1/2 rounded-lg border border-red-500/30 bg-red-500/20 px-4 py-2 text-sm text-red-300 shadow-lg">
          {toast}
        </div>
      )}

      {showAddModal && <AddApplicationModal onClose={() => setShowAddModal(false)} onAdd={handleAdd} />}
    </div>
  );
}
