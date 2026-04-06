import { LockKeyhole, Sparkles } from "lucide-react";
import { useEffect, useState } from "react";

import { api } from "../services/api";
import { JournalEntryDecrypted, JournalEntryMeta } from "../types/api";

export default function JournalPage() {
  const [tab, setTab] = useState<"write" | "read">("write");
  const [entries, setEntries] = useState<JournalEntryMeta[]>([]);
  const [content, setContent] = useState("");
  const [passphrase, setPassphrase] = useState("");
  const [mood, setMood] = useState("");
  const [tags, setTags] = useState("");
  const [selected, setSelected] = useState<JournalEntryDecrypted | null>(null);
  const [readPassphrase, setReadPassphrase] = useState("");
  const [activeEntryId, setActiveEntryId] = useState<string | null>(null);
  const [error, setError] = useState("");

  const load = async () => {
    const list = await api.journal.list({ limit: 100, offset: 0 });
    setEntries(list);
  };

  useEffect(() => {
    void load();
  }, []);

  const onSave = async () => {
    setError("");
    try {
      await api.journal.create({
        content,
        passphrase,
        mood: mood || undefined,
        tags: tags
          .split(",")
          .map((tag) => tag.trim())
          .filter(Boolean),
      });
      setContent("");
      setPassphrase("");
      setMood("");
      setTags("");
      setTab("read");
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to save entry");
    }
  };

  const onDecrypt = async (entryId: string) => {
    setError("");
    try {
      const entry = await api.journal.read(entryId, readPassphrase);
      setSelected(entry);
      setActiveEntryId(entryId);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to decrypt entry");
    }
  };

  const onGenerateSummary = async (entryId: string) => {
    setError("");
    try {
      const entry = await api.journal.summary(entryId, readPassphrase);
      setSelected(entry);
      setActiveEntryId(entryId);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to generate summary");
    }
  };

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-bold">Journal Vault</h1>
        <p className="text-sm text-[rgb(var(--text-dim))]">Capture your day with encrypted journaling.</p>
      </header>

      <div className="inline-flex rounded-xl border border-[rgb(var(--border))] p-1">
        <button
          type="button"
          onClick={() => setTab("write")}
          className={`rounded-lg px-3 py-1.5 text-sm ${tab === "write" ? "bg-[rgb(var(--primary))] text-white" : ""}`}
        >
          Write
        </button>
        <button
          type="button"
          onClick={() => setTab("read")}
          className={`rounded-lg px-3 py-1.5 text-sm ${tab === "read" ? "bg-[rgb(var(--primary))] text-white" : ""}`}
        >
          Read
        </button>
      </div>

      {tab === "write" ? (
        <section className="card space-y-4 p-4">
          <div className="flex items-center gap-2 rounded-xl border border-emerald-500/40 bg-emerald-500/10 px-3 py-2 text-sm text-emerald-400">
            <LockKeyhole className="h-4 w-4" /> AES-256-GCM encrypted
          </div>
          <textarea
            value={content}
            onChange={(event) => setContent(event.target.value)}
            placeholder="Write your thoughts..."
            className="h-44 w-full rounded-xl border border-[rgb(var(--border))] bg-[rgb(var(--bg-muted))] p-3"
          />

          <div className="grid gap-3 md:grid-cols-3">
            <label className="space-y-1">
              <span className="text-sm font-medium">Mood</span>
              <select
                value={mood}
                onChange={(event) => setMood(event.target.value)}
                className="w-full rounded-xl border border-[rgb(var(--border))] bg-[rgb(var(--bg-muted))] px-3 py-2"
              >
                <option value="">Select mood</option>
                <option value="happy">😀 Happy</option>
                <option value="calm">😌 Calm</option>
                <option value="focused">🧠 Focused</option>
                <option value="anxious">😟 Anxious</option>
                <option value="sad">😢 Sad</option>
              </select>
            </label>
            <label className="space-y-1">
              <span className="text-sm font-medium">Tags</span>
              <input
                value={tags}
                onChange={(event) => setTags(event.target.value)}
                placeholder="work, health"
                className="w-full rounded-xl border border-[rgb(var(--border))] bg-[rgb(var(--bg-muted))] px-3 py-2"
              />
            </label>
            <label className="space-y-1">
              <span className="text-sm font-medium">Passphrase</span>
              <input
                type="password"
                value={passphrase}
                onChange={(event) => setPassphrase(event.target.value)}
                className="w-full rounded-xl border border-[rgb(var(--border))] bg-[rgb(var(--bg-muted))] px-3 py-2"
              />
            </label>
          </div>

          {error ? <p className="text-sm text-[rgb(var(--danger))]">{error}</p> : null}
          <button
            type="button"
            onClick={() => void onSave()}
            className="rounded-xl bg-[rgb(var(--primary))] px-4 py-2 text-sm font-semibold text-white"
          >
            Encrypt & Save
          </button>
        </section>
      ) : (
        <div className="grid gap-4 lg:grid-cols-2">
          <section className="card p-4">
            <h2 className="mb-3 text-lg font-semibold">Entries</h2>
            <div className="space-y-2">
              {entries.map((entry) => (
                <article key={entry.id} className="rounded-xl border border-[rgb(var(--border))] bg-[rgb(var(--bg-muted))] p-3">
                  <div className="flex items-center justify-between gap-2">
                    <p className="text-sm font-medium">{entry.entry_date}</p>
                    <span className="text-xs text-[rgb(var(--text-dim))]">{entry.word_count || 0} words</span>
                  </div>
                  <p className="mt-1 text-xs text-[rgb(var(--text-dim))]">{(entry.tags || []).join(", ") || "No tags"}</p>
                  <div className="mt-2 flex flex-wrap gap-2">
                    <button
                      type="button"
                      onClick={() => {
                        setSelected(null);
                        setActiveEntryId(entry.id);
                      }}
                      className="rounded-lg border border-[rgb(var(--border))] px-2 py-1 text-xs"
                    >
                      Select
                    </button>
                    <button
                      type="button"
                      onClick={() => void onGenerateSummary(entry.id)}
                      className="inline-flex items-center gap-1 rounded-lg bg-[rgb(var(--primary))]/20 px-2 py-1 text-xs font-medium text-[rgb(var(--primary))]"
                    >
                      <Sparkles className="h-3.5 w-3.5" /> AI Summary
                    </button>
                  </div>
                </article>
              ))}
            </div>
          </section>

          <section className="card p-4">
            <h2 className="mb-3 text-lg font-semibold">Decrypt entry</h2>
            <label className="block space-y-1">
              <span className="text-sm font-medium">Passphrase</span>
              <input
                type="password"
                value={readPassphrase}
                onChange={(event) => setReadPassphrase(event.target.value)}
                className="w-full rounded-xl border border-[rgb(var(--border))] bg-[rgb(var(--bg-muted))] px-3 py-2"
              />
            </label>
            <button
              type="button"
              disabled={!activeEntryId}
              onClick={() => activeEntryId && void onDecrypt(activeEntryId)}
              className="mt-3 rounded-xl bg-[rgb(var(--primary))] px-4 py-2 text-sm font-semibold text-white disabled:opacity-50"
            >
              Decrypt
            </button>

            {selected ? (
              <article className="mt-4 rounded-xl border border-[rgb(var(--border))] bg-[rgb(var(--bg-muted))] p-3">
                <p className="text-xs text-[rgb(var(--text-dim))]">{selected.entry_date}</p>
                <p className="mt-2 whitespace-pre-wrap text-sm">{selected.content}</p>
                {selected.summary ? (
                  <div className="mt-3 rounded-lg bg-blue-500/10 p-2 text-xs text-blue-300">Summary: {selected.summary}</div>
                ) : null}
              </article>
            ) : null}

            {error ? <p className="mt-2 text-sm text-[rgb(var(--danger))]">{error}</p> : null}
          </section>
        </div>
      )}
    </div>
  );
}
