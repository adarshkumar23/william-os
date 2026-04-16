import { motion, useReducedMotion } from "framer-motion";
import { LockKeyhole, Sparkles } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { fadeInUp, reduceMotion, staggerContainer } from "../lib/animations";
import { api } from "../services/api";
import { JournalEntryDecrypted, JournalEntryMeta } from "../types/api";
import { AppCard, EmptyState, SectionHeader, SkeletonLoader } from "../components/ui";

const moodScore: Record<string, number> = {
  great: 9,
  good: 7,
  okay: 6,
  low: 4,
  bad: 3,
};

const moodIcon: Record<string, string> = {
  great: "☀️",
  good: "🌤",
  okay: "⛅",
  low: "🌧",
  bad: "⛈️",
};

export default function JournalPage() {
  const [tab, setTab] = useState<"write" | "read">("write");
  const [entries, setEntries] = useState<JournalEntryMeta[]>([]);
  const [content, setContent] = useState("");
  const [passphrase, setPassphrase] = useState("");
  const [mood, setMood] = useState("");
  const [tags, setTags] = useState("");
  const [selected, setSelected] = useState<JournalEntryDecrypted | null>(null);
  const [readPassphrase, setReadPassphrase] = useState("");
  const [unlockPassphrase, setUnlockPassphrase] = useState("");
  const [unlockExpiresAt, setUnlockExpiresAt] = useState<string | null>(null);
  const [draftSavedAt, setDraftSavedAt] = useState<string | null>(null);
  const [activeEntryId, setActiveEntryId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [draftSaving, setDraftSaving] = useState(false);
  const [error, setError] = useState("");

  const shouldReduceMotion = useReducedMotion();
  const fadeMotion = reduceMotion(shouldReduceMotion, fadeInUp);
  const isJournalUnlocked = Boolean(unlockExpiresAt && new Date(unlockExpiresAt) > new Date());

  const load = async () => {
    setLoading(true);
    const list = await api.journal.list({ limit: 100, offset: 0 });
    setEntries(list);
    setLoading(false);
  };

  const hydrateServerDraft = async (passphraseOverride?: string) => {
    try {
      const draft = await api.journal.getDraft(passphraseOverride);
      if (!draft) {
        return;
      }
      setContent(draft.content || "");
      setMood(String(draft.mood || ""));
      setTags((draft.tags || []).join(", "));
      setDraftSavedAt(draft.updated_at);
    } catch {
      // Draft may be encrypted and vault locked. Ignore until unlocked/passphrase is provided.
    }
  };

  useEffect(() => {
    void load();
    void hydrateServerDraft();
  }, []);

  useEffect(() => {
    if (tab !== "write") {
      return;
    }
    if (!isJournalUnlocked && !passphrase.trim()) {
      return;
    }

    const timer = window.setTimeout(async () => {
      if (!content.trim() && !mood && !tags.trim()) {
        try {
          await api.journal.clearDraft();
          setDraftSavedAt(null);
        } catch {
          // no-op
        }
        return;
      }

      setDraftSaving(true);
      try {
        const payload = {
          content,
          passphrase: passphrase || undefined,
          mood: mood || undefined,
          tags: tags
            .split(",")
            .map((tag) => tag.trim())
            .filter(Boolean),
        };
        const saved = await api.journal.saveDraft(payload);
        setDraftSavedAt(saved.updated_at);
      } catch {
        // Keep typing uninterrupted if autosave fails.
      } finally {
        setDraftSaving(false);
      }
    }, 700);

    return () => window.clearTimeout(timer);
  }, [tab, content, mood, tags, passphrase, isJournalUnlocked]);

  const onSave = async () => {
    setError("");
    try {
      await api.journal.create({
        content,
        passphrase: passphrase || undefined,
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
      await api.journal.clearDraft();
      setDraftSavedAt(null);
      setTab("read");
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to save entry");
    }
  };

  const onUnlock = async () => {
    setError("");
    try {
      const response = await api.journal.unlock(unlockPassphrase);
      setUnlockExpiresAt(response.unlock_expires_at);
      setPassphrase("");
      setReadPassphrase("");
      await hydrateServerDraft();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to unlock journal");
    }
  };

  const onDecrypt = async (entryId: string) => {
    setError("");
    try {
      const entry = await api.journal.read(entryId, readPassphrase || undefined);
      setSelected(entry);
      setActiveEntryId(entryId);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to decrypt entry");
    }
  };

  const onGenerateSummary = async (entryId: string) => {
    setError("");
    try {
      const entry = await api.journal.summary(entryId, readPassphrase || undefined);
      setSelected(entry);
      setActiveEntryId(entryId);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to generate summary");
    }
  };

  const trendData = useMemo(
    () =>
      entries
        .slice(0, 12)
        .reverse()
        .map((entry) => ({
          date: entry.entry_date.slice(5),
          mood: moodScore[String(entry.mood || "").toLowerCase()] || 5,
        })),
    [entries],
  );

  return (
    <div className="space-y-6">
      <SectionHeader
        title="Journal"
        subtitle="Encrypted reflection with mood context and summary intelligence."
        action={
          <div className="inline-flex rounded-lg border border-border bg-surface p-1">
            <button
              type="button"
              onClick={() => setTab("write")}
              className={`rounded-md px-3 py-1.5 text-xs ${tab === "write" ? "bg-accent text-white" : "text-text-secondary"}`}
            >
              Write
            </button>
            <button
              type="button"
              onClick={() => setTab("read")}
              className={`rounded-md px-3 py-1.5 text-xs ${tab === "read" ? "bg-accent text-white" : "text-text-secondary"}`}
            >
              Read
            </button>
          </div>
        }
      />

      <motion.section variants={staggerContainer} initial="initial" animate="animate" className="grid gap-4 lg:grid-cols-3">
        <motion.div variants={fadeMotion}>
          <AppCard hover>
            <p className="section-label">Entries</p>
            <p className="stat-number mt-3">{entries.length}</p>
          </AppCard>
        </motion.div>
        <motion.div variants={fadeMotion} className="lg:col-span-2">
          <AppCard>
            <p className="section-label">Mood Trend</p>
            <div className="mt-3 h-40">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={trendData}>
                  <XAxis dataKey="date" stroke="rgb(var(--color-text-muted))" tick={{ fontSize: 11 }} />
                  <YAxis domain={[0, 10]} stroke="rgb(var(--color-text-muted))" tick={{ fontSize: 11 }} />
                  <Tooltip />
                  <Line type="monotone" dataKey="mood" stroke="rgb(var(--color-accent))" strokeWidth={2.5} dot={false} />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </AppCard>
        </motion.div>
      </motion.section>

      {tab === "write" ? (
        <AppCard className="bg-[#1b1815]" padding="lg">
          <div className="mb-3 flex items-center gap-2 rounded-lg border border-success/40 bg-success/10 px-3 py-2 text-sm text-success">
            <LockKeyhole className="h-4 w-4" /> AES-256-GCM encrypted
          </div>
          <div className="mb-3 grid gap-3 rounded-lg border border-border bg-surface-raised p-3 md:grid-cols-[1fr_auto]">
            <div className="space-y-2">
              <p className="text-xs font-semibold uppercase tracking-wide text-text-secondary">Vault Unlock</p>
              <input
                type="password"
                value={unlockPassphrase}
                onChange={(event) => setUnlockPassphrase(event.target.value)}
                placeholder="Unlock passphrase"
                className="w-full rounded-input border border-border bg-surface px-3 py-2 text-sm"
              />
              <p className="text-xs text-text-muted">
                {isJournalUnlocked
                  ? `Unlocked until ${new Date(unlockExpiresAt as string).toLocaleTimeString()}`
                  : "Unlock once to save/read without repeating passphrase for this session."}
              </p>
            </div>
            <button
              type="button"
              onClick={() => void onUnlock()}
              disabled={!unlockPassphrase.trim()}
              className="h-fit self-end rounded-button border border-border px-3 py-2 text-xs font-semibold text-text-primary disabled:opacity-50"
            >
              Unlock
            </button>
          </div>
          <textarea
            value={content}
            onChange={(event) => setContent(event.target.value)}
            placeholder="Write your thoughts..."
            className="h-72 w-full rounded-input border border-border bg-[#24201d] p-4 text-sm leading-relaxed text-text-primary outline-none"
          />
          <div className="mt-3 grid gap-3 md:grid-cols-3">
            <select
              value={mood}
              onChange={(event) => setMood(event.target.value)}
              className="rounded-input border border-border bg-surface-raised px-3 py-2 text-sm text-text-primary"
            >
              <option value="">Mood</option>
              <option value="great">☀️ Great</option>
              <option value="good">🌤 Good</option>
              <option value="okay">⛅ Okay</option>
              <option value="low">🌧 Low</option>
              <option value="bad">⛈️ Bad</option>
            </select>
            <input
              value={tags}
              onChange={(event) => setTags(event.target.value)}
              placeholder="tags, comma,separated"
              className="rounded-input border border-border bg-surface-raised px-3 py-2 text-sm"
            />
            <input
              type="password"
              value={passphrase}
              onChange={(event) => setPassphrase(event.target.value)}
              placeholder="Passphrase (optional if unlocked)"
              className="rounded-input border border-border bg-surface-raised px-3 py-2 text-sm"
            />
          </div>
          {draftSaving ? <p className="mt-2 text-xs text-text-muted">Saving draft...</p> : null}
          {draftSavedAt ? <p className="mt-2 text-xs text-text-muted">Draft saved at {new Date(draftSavedAt).toLocaleTimeString()}</p> : null}
          {error ? <p className="mt-2 text-sm text-danger">{error}</p> : null}
          <button
            type="button"
            onClick={() => void onSave()}
            disabled={!content.trim() || (!passphrase.trim() && !isJournalUnlocked)}
            className="mt-4 rounded-button bg-accent px-4 py-2 text-sm font-semibold text-white"
          >
            Save Entry
          </button>
        </AppCard>
      ) : loading ? (
        <div className="space-y-2">
          {Array.from({ length: 4 }).map((_, idx) => (
            <SkeletonLoader key={idx} variant="card" />
          ))}
        </div>
      ) : entries.length === 0 ? (
        <EmptyState
          icon={<NotebookSpark />}
          title="No journal entries yet"
          description="Start writing to unlock encrypted history and mood trends."
          action={
            <button
              type="button"
              onClick={() => setTab("write")}
              className="rounded-button bg-accent px-4 py-2 text-sm font-semibold text-white"
            >
              Write Entry
            </button>
          }
        />
      ) : (
        <div className="grid gap-4 lg:grid-cols-2">
          <AppCard>
            <p className="section-label">Entry List</p>
            <div className="mt-4 space-y-2">
              {entries.map((entry) => (
                <div key={entry.id} className="rounded-lg border border-border bg-surface-raised p-3">
                  <div className="flex items-center justify-between gap-2">
                    <p className="text-sm font-medium text-text-primary">{entry.entry_date}</p>
                    <p className="text-sm">{moodIcon[String(entry.mood || "").toLowerCase()] || "⛅"}</p>
                  </div>
                  <p className={`mt-2 text-sm text-text-secondary ${selected?.id === entry.id ? "" : "blur-sm"}`}>
                    Encrypted entry preview. Unlock with passphrase.
                  </p>
                  <div className="mt-3 flex gap-2">
                    <button
                      type="button"
                      onClick={() => {
                        setSelected(null);
                        setActiveEntryId(entry.id);
                      }}
                      className="rounded-button border border-border px-3 py-1.5 text-xs text-text-secondary"
                    >
                      Select
                    </button>
                    <button
                      type="button"
                      onClick={() => void onGenerateSummary(entry.id)}
                      className="inline-flex items-center gap-1 rounded-button bg-accent/15 px-3 py-1.5 text-xs text-accent"
                    >
                      <Sparkles className="h-3.5 w-3.5" /> Summary
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </AppCard>

          <AppCard>
            <p className="section-label">Decrypt Entry</p>
            <p className="mt-2 text-xs text-text-muted">
              {isJournalUnlocked
                ? `Vault unlocked until ${new Date(unlockExpiresAt as string).toLocaleTimeString()}. Passphrase optional.`
                : "Provide passphrase or unlock vault from Write tab."}
            </p>
            <input
              type="password"
              value={readPassphrase}
              onChange={(event) => setReadPassphrase(event.target.value)}
              placeholder="Passphrase (optional if unlocked)"
              className="mt-3 w-full rounded-input border border-border bg-surface-raised px-3 py-2 text-sm"
            />
            <button
              type="button"
              disabled={!activeEntryId}
              onClick={() => activeEntryId && void onDecrypt(activeEntryId)}
              className="mt-3 rounded-button bg-accent px-4 py-2 text-sm font-semibold text-white disabled:opacity-50"
            >
              Decrypt
            </button>

            {selected ? (
              <article className="mt-4 rounded-lg border border-border bg-surface-raised p-3">
                <p className="meta-copy">{selected.entry_date}</p>
                <p className="mt-2 whitespace-pre-wrap text-sm text-text-primary">{selected.content}</p>
                {selected.summary ? <p className="mt-3 text-xs text-info">Summary: {selected.summary}</p> : null}
              </article>
            ) : null}

            {error ? <p className="mt-2 text-sm text-danger">{error}</p> : null}
          </AppCard>
        </div>
      )}
    </div>
  );
}

function NotebookSpark() {
  return <Sparkles className="h-6 w-6" />;
}
