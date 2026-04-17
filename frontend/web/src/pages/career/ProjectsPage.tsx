import clsx from "clsx";
import { ExternalLink, Github, Plus, Star } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { api } from "../../services/api";

type Project = {
  id: string;
  name: string;
  description: string | null;
  tech_stack: string[];
  status: string;
  live_url: string | null;
  github_url: string | null;
  on_resume: boolean;
  started_at: string | null;
  shipped_at: string | null;
};

const STATUS_ORDER = ["deployed", "on_resume", "building", "planning", "archived"];

const STATUS_COLORS: Record<string, string> = {
  deployed: "bg-green-500/15 text-green-300",
  on_resume: "bg-indigo-500/15 text-indigo-300",
  building: "bg-amber-500/15 text-amber-300",
  planning: "bg-blue-500/15 text-blue-300",
  archived: "bg-zinc-500/15 text-zinc-400",
};

const TECH_CATEGORY_COLORS: Record<string, string> = {
  react: "bg-cyan-500/15 text-cyan-300",
  typescript: "bg-blue-500/15 text-blue-300",
  python: "bg-yellow-500/15 text-yellow-300",
  fastapi: "bg-teal-500/15 text-teal-300",
  nodejs: "bg-green-500/15 text-green-300",
  nextjs: "bg-zinc-500/15 text-zinc-300",
  postgres: "bg-indigo-500/15 text-indigo-300",
  default: "bg-surface-raised text-text-secondary",
};

function techColor(tech: string): string {
  const lower = tech.toLowerCase();
  return TECH_CATEGORY_COLORS[lower] ?? TECH_CATEGORY_COLORS.default;
}

function AddProjectModal({ onClose, onAdd }: { onClose: () => void; onAdd: (p: Project) => void }) {
  const [form, setForm] = useState({ name: "", description: "", tech_stack: "", status: "planning", live_url: "", github_url: "" });
  const [saving, setSaving] = useState(false);

  const submit = async () => {
    if (!form.name) return;
    setSaving(true);
    try {
      const result = await api.career.createProject({
        name: form.name,
        description: form.description || null,
        tech_stack: form.tech_stack ? form.tech_stack.split(",").map((t) => t.trim()).filter(Boolean) : [],
        status: form.status,
        live_url: form.live_url || null,
        github_url: form.github_url || null,
      });
      onAdd(result as Project);
      onClose();
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="w-[480px] rounded-xl border border-border bg-surface p-6 shadow-2xl">
        <h3 className="mb-4 font-semibold text-text-primary">Add Project</h3>
        <div className="space-y-3">
          {[
            { key: "name", label: "Name", placeholder: "My Awesome Project" },
            { key: "description", label: "Description", placeholder: "What does it do?" },
            { key: "tech_stack", label: "Tech Stack (comma-separated)", placeholder: "React, TypeScript, FastAPI" },
            { key: "live_url", label: "Live URL", placeholder: "https://..." },
            { key: "github_url", label: "GitHub URL", placeholder: "https://github.com/..." },
          ].map(({ key, label, placeholder }) => (
            <div key={key}>
              <label className="mb-1 block text-xs text-text-secondary">{label}</label>
              <input className="w-full rounded-lg border border-border bg-surface-raised px-3 py-2 text-sm text-text-primary placeholder-text-secondary focus:border-indigo-400 focus:outline-none" placeholder={placeholder} value={(form as Record<string, string>)[key]} onChange={(e) => setForm((f) => ({ ...f, [key]: e.target.value }))} />
            </div>
          ))}
          <div>
            <label className="mb-1 block text-xs text-text-secondary">Status</label>
            <select className="w-full rounded-lg border border-border bg-surface-raised px-3 py-2 text-sm text-text-primary focus:outline-none" value={form.status} onChange={(e) => setForm((f) => ({ ...f, status: e.target.value }))}>
              {STATUS_ORDER.map((s) => <option key={s} value={s}>{s}</option>)}
            </select>
          </div>
        </div>
        <div className="mt-4 flex gap-2">
          <button className="flex-1 rounded-lg border border-border px-4 py-2 text-sm text-text-secondary hover:bg-surface-raised" onClick={onClose}>Cancel</button>
          <button className="flex-1 rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-500 disabled:opacity-50" onClick={submit} disabled={saving || !form.name}>{saving ? "Adding..." : "Add"}</button>
        </div>
      </div>
    </div>
  );
}

export default function ProjectsPage() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(true);
  const [showModal, setShowModal] = useState(false);

  const load = useCallback(async () => {
    try {
      const result = await api.career.listProjects();
      setProjects(result as Project[]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { void load(); }, [load]);

  const sortedProjects = [...projects].sort((a, b) => STATUS_ORDER.indexOf(a.status) - STATUS_ORDER.indexOf(b.status));

  const toggleResume = async (project: Project) => {
    const updated = await api.career.updateProject(project.id, { on_resume: !project.on_resume });
    setProjects((prev) => prev.map((p) => p.id === project.id ? { ...p, ...(updated as Project) } : p));
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-text-primary">Projects</h1>
          <p className="meta-copy mt-1">{projects.filter((p) => p.status === "deployed" || p.status === "on_resume").length} deployed · {projects.filter((p) => p.on_resume).length} on resume</p>
        </div>
        <button onClick={() => setShowModal(true)} className="flex items-center gap-2 rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-500">
          <Plus className="h-4 w-4" /> Add Project
        </button>
      </div>

      {loading ? (
        <div className="flex h-32 items-center justify-center">
          <div className="h-6 w-6 animate-spin rounded-full border-2 border-indigo-500 border-t-transparent" />
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {sortedProjects.length === 0 && (
            <p className="col-span-3 py-8 text-center text-text-secondary">No projects yet</p>
          )}
          {sortedProjects.map((project) => (
            <div key={project.id} className={clsx("rounded-xl border border-border bg-surface p-4", project.status === "archived" && "opacity-60")}>
              <div className="flex items-start justify-between gap-2">
                <h3 className="font-semibold text-text-primary">{project.name}</h3>
                <span className={clsx("shrink-0 rounded-full px-2 py-0.5 text-[10px] capitalize", STATUS_COLORS[project.status] ?? "")}>{project.status}</span>
              </div>
              {project.description && <p className="mt-1 text-xs text-text-secondary line-clamp-2">{project.description}</p>}
              <div className="mt-3 flex flex-wrap gap-1">
                {project.tech_stack.map((t) => <span key={t} className={clsx("rounded-full px-2 py-0.5 text-[10px]", techColor(t))}>{t}</span>)}
              </div>
              <div className="mt-3 flex items-center gap-2">
                {project.live_url && <a href={project.live_url} target="_blank" rel="noopener noreferrer" className="text-text-secondary hover:text-indigo-300"><ExternalLink className="h-4 w-4" /></a>}
                {project.github_url && <a href={project.github_url} target="_blank" rel="noopener noreferrer" className="text-text-secondary hover:text-text-primary"><Github className="h-4 w-4" /></a>}
                <button onClick={() => toggleResume(project)} className={clsx("ml-auto flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] transition", project.on_resume ? "bg-indigo-500/20 text-indigo-300" : "bg-surface-raised text-text-secondary hover:text-text-primary")}>
                  <Star className="h-3 w-3" /> On Resume
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {showModal && <AddProjectModal onClose={() => setShowModal(false)} onAdd={(p) => setProjects((prev) => [p, ...prev])} />}
    </div>
  );
}
