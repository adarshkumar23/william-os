import clsx from "clsx";
import { Copy, Plus, X } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { api } from "../../services/api";

type Contact = {
  id: string;
  name: string;
  company: string | null;
  role: string | null;
  tags: string[];
  linkedin_url: string | null;
  email: string | null;
  temperature: string;
  last_contacted_at: string | null;
  next_followup_at: string | null;
  relationship_notes: string | null;
};

const TEMP_COLORS: Record<string, string> = {
  cold: "bg-zinc-500/15 text-zinc-300",
  warm: "bg-amber-500/15 text-amber-300",
  hot: "bg-red-500/15 text-red-300",
};

function DraftMessageModal({ contact, onClose }: { contact: Contact; onClose: () => void }) {
  const [context, setContext] = useState("");
  const [draft, setDraft] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [copied, setCopied] = useState(false);

  const generate = async () => {
    setLoading(true);
    try {
      const result = await api.career.draftContactMessage(contact.id, context || undefined);
      setDraft(result.draft);
    } finally {
      setLoading(false);
    }
  };

  const copy = () => {
    if (draft) { navigator.clipboard.writeText(draft); setCopied(true); setTimeout(() => setCopied(false), 2000); }
  };

  const markContacted = async () => {
    await api.career.updateContact(contact.id, { last_contacted_at: new Date().toISOString().split("T")[0] });
    onClose();
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="w-[520px] rounded-xl border border-border bg-surface p-6 shadow-2xl">
        <div className="mb-4 flex items-center justify-between">
          <h3 className="font-semibold text-text-primary">Draft message to {contact.name}</h3>
          <button onClick={onClose}><X className="h-4 w-4 text-text-secondary" /></button>
        </div>
        <div className="mb-3">
          <label className="mb-1 block text-xs text-text-secondary">Context (optional)</label>
          <input className="w-full rounded-lg border border-border bg-surface-raised px-3 py-2 text-sm text-text-primary focus:border-indigo-400 focus:outline-none" placeholder="e.g. following up on our conversation about ML roles" value={context} onChange={(e) => setContext(e.target.value)} />
        </div>
        {!draft && (
          <button onClick={generate} disabled={loading} className="w-full rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-500 disabled:opacity-50">
            {loading ? "Generating..." : "Generate with Gemini"}
          </button>
        )}
        {draft && (
          <div className="space-y-3">
            <div className="rounded-lg border border-border bg-surface-raised p-4 text-sm text-text-primary">{draft}</div>
            <div className="flex gap-2">
              <button onClick={copy} className="flex items-center gap-2 rounded-lg border border-border px-4 py-2 text-sm text-text-secondary hover:bg-surface-raised">
                <Copy className="h-4 w-4" /> {copied ? "Copied!" : "Copy"}
              </button>
              <button onClick={markContacted} className="flex-1 rounded-lg bg-green-600 px-4 py-2 text-sm font-medium text-white hover:bg-green-500">
                Mark Contacted
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function AddContactModal({ onClose, onAdd }: { onClose: () => void; onAdd: (c: Contact) => void }) {
  const [form, setForm] = useState({ name: "", company: "", role: "", linkedin_url: "", email: "", temperature: "cold", relationship_notes: "" });
  const [saving, setSaving] = useState(false);

  const submit = async () => {
    if (!form.name) return;
    setSaving(true);
    try {
      const result = await api.career.createContact({ ...form, company: form.company || null, role: form.role || null, linkedin_url: form.linkedin_url || null, email: form.email || null, relationship_notes: form.relationship_notes || null });
      onAdd(result as Contact);
      onClose();
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="w-[480px] rounded-xl border border-border bg-surface p-6 shadow-2xl">
        <h3 className="mb-4 font-semibold text-text-primary">Add Contact</h3>
        <div className="space-y-3">
          {[
            { key: "name", label: "Name", placeholder: "Rahul Sharma" },
            { key: "company", label: "Company", placeholder: "Google" },
            { key: "role", label: "Role", placeholder: "SDE-2" },
            { key: "linkedin_url", label: "LinkedIn URL", placeholder: "https://linkedin.com/in/..." },
            { key: "email", label: "Email", placeholder: "rahul@example.com" },
            { key: "relationship_notes", label: "Notes", placeholder: "Met at hackathon..." },
          ].map(({ key, label, placeholder }) => (
            <div key={key}>
              <label className="mb-1 block text-xs text-text-secondary">{label}</label>
              <input className="w-full rounded-lg border border-border bg-surface-raised px-3 py-2 text-sm text-text-primary placeholder-text-secondary focus:border-indigo-400 focus:outline-none" placeholder={placeholder} value={(form as Record<string, string>)[key]} onChange={(e) => setForm((f) => ({ ...f, [key]: e.target.value }))} />
            </div>
          ))}
          <div>
            <label className="mb-1 block text-xs text-text-secondary">Temperature</label>
            <select className="w-full rounded-lg border border-border bg-surface-raised px-3 py-2 text-sm text-text-primary focus:outline-none" value={form.temperature} onChange={(e) => setForm((f) => ({ ...f, temperature: e.target.value }))}>
              {["cold", "warm", "hot"].map((t) => <option key={t} value={t}>{t}</option>)}
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

export default function NetworkPage() {
  const [contacts, setContacts] = useState<Contact[]>([]);
  const [followups, setFollowups] = useState<Contact[]>([]);
  const [loading, setLoading] = useState(true);
  const [showModal, setShowModal] = useState(false);
  const [draftContact, setDraftContact] = useState<Contact | null>(null);
  const [filterTemp, setFilterTemp] = useState("");

  const load = useCallback(async () => {
    try {
      const [all, fups] = await Promise.all([api.career.listContacts(), api.career.getContactFollowups()]);
      setContacts(all as Contact[]);
      setFollowups(fups as Contact[]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { void load(); }, [load]);

  const filtered = filterTemp ? contacts.filter((c) => c.temperature === filterTemp) : contacts;

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-text-primary">Network</h1>
          <p className="meta-copy mt-1">{contacts.length} contacts · {followups.length} due for follow-up</p>
        </div>
        <button onClick={() => setShowModal(true)} className="flex items-center gap-2 rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-500">
          <Plus className="h-4 w-4" /> Add Contact
        </button>
      </div>

      <div className="grid grid-cols-3 gap-4">
        {/* Contact list */}
        <div className="col-span-2 space-y-3">
          <div className="flex gap-2">
            {["", "cold", "warm", "hot"].map((t) => (
              <button key={t} onClick={() => setFilterTemp(t)} className={clsx("rounded-full px-3 py-1 text-xs capitalize", filterTemp === t ? "bg-indigo-500/20 text-indigo-300 border border-indigo-400/40" : "bg-surface border border-border text-text-secondary hover:bg-surface-raised")}>
                {t || "All"}
              </button>
            ))}
          </div>
          {loading ? (
            <div className="flex h-32 items-center justify-center"><div className="h-6 w-6 animate-spin rounded-full border-2 border-indigo-500 border-t-transparent" /></div>
          ) : filtered.length === 0 ? (
            <p className="py-8 text-center text-text-secondary">No contacts</p>
          ) : (
            <div className="space-y-2">
              {filtered.map((c) => (
                <div key={c.id} className="flex items-center gap-3 rounded-xl border border-border bg-surface p-3">
                  <div className="grid h-9 w-9 shrink-0 place-items-center rounded-full bg-indigo-500/15 text-sm font-semibold text-indigo-300">
                    {c.name.charAt(0).toUpperCase()}
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      <p className="font-medium text-text-primary text-sm">{c.name}</p>
                      <span className={clsx("rounded-full px-2 py-0.5 text-[10px]", TEMP_COLORS[c.temperature])}>{c.temperature}</span>
                    </div>
                    <p className="text-xs text-text-secondary truncate">{[c.role, c.company].filter(Boolean).join(" @ ")}</p>
                  </div>
                  {c.linkedin_url && <a href={c.linkedin_url} target="_blank" rel="noopener noreferrer" className="text-xs text-indigo-400 hover:text-indigo-300 shrink-0">LinkedIn</a>}
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Follow-up queue */}
        <div className="rounded-xl border border-border bg-surface p-4">
          <h3 className="mb-3 font-semibold text-text-primary">Reach out this week</h3>
          {followups.length === 0 ? (
            <p className="meta-copy text-center py-4">No follow-ups due</p>
          ) : (
            <div className="space-y-2">
              {followups.map((c) => (
                <div key={c.id} className="rounded-lg border border-border bg-surface-raised p-3">
                  <div className="flex items-center justify-between">
                    <p className="text-sm font-medium text-text-primary">{c.name}</p>
                    <span className={clsx("rounded-full px-2 py-0.5 text-[10px]", TEMP_COLORS[c.temperature])}>{c.temperature}</span>
                  </div>
                  <p className="mt-0.5 text-xs text-text-secondary">{c.company ?? ""}</p>
                  <button onClick={() => setDraftContact(c)} className="mt-2 w-full rounded-lg bg-indigo-500/15 py-1.5 text-xs text-indigo-300 hover:bg-indigo-500/25">
                    Draft Message
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {showModal && <AddContactModal onClose={() => setShowModal(false)} onAdd={(c) => setContacts((prev) => [c, ...prev])} />}
      {draftContact && <DraftMessageModal contact={draftContact} onClose={() => { setDraftContact(null); void load(); }} />}
    </div>
  );
}
