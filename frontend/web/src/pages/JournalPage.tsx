import { useEffect, useState } from "react";

import JournalEditor, { JournalDraft } from "../components/JournalEditor";
import { api } from "../services/api";

export default function JournalPage() {
  const [entries, setEntries] = useState<any[]>([]);
  const [selectedEntry, setSelectedEntry] = useState<any | null>(null);
  const [readPassphrase, setReadPassphrase] = useState("");
  const [error, setError] = useState<string | null>(null);

  const load = async () => {
    const data = await api.journal.list();
    setEntries(data);
  };

  useEffect(() => {
    void load();
  }, []);

  const handleCreate = async (draft: JournalDraft) => {
    setError(null);
    try {
      await api.journal.create(draft);
      await load();
    } catch (err: any) {
      setError(err?.response?.data?.error || "Failed to save journal entry");
    }
  };

  return (
    <div className="grid gap-5 xl:grid-cols-[1.3fr_1fr]">
      <div className="space-y-5">
        <JournalEditor onSubmit={handleCreate} />
        {error && <p className="text-sm text-red-600">{error}</p>}

        {selectedEntry && (
          <div className="panel p-4">
            <h3 className="font-display text-xl font-bold">Decrypted Entry</h3>
            <p className="mt-2 whitespace-pre-wrap text-sm leading-relaxed">{selectedEntry.content}</p>
            {selectedEntry.summary && (
              <p className="mt-4 rounded-xl bg-slate-100 p-3 text-sm dark:bg-slate-800">
                Summary: {selectedEntry.summary}
              </p>
            )}
          </div>
        )}
      </div>

      <aside className="panel p-4">
        <h2 className="font-display text-xl font-bold">Past Entries</h2>
        <div className="mt-3 space-y-2">
          {entries.map((entry) => (
            <div key={entry.id} className="rounded-xl border border-slate-200 p-3 dark:border-slate-700">
              <p className="text-xs text-slate-500 dark:text-slate-400">{entry.entry_date} • {entry.mood || "-"}</p>
              <p className="text-sm">{entry.word_count || 0} words</p>
              <div className="mt-2 flex gap-2">
                <input
                  className="w-full rounded-lg border border-slate-300 bg-white/80 px-2 py-1 text-sm dark:border-slate-700 dark:bg-slate-900"
                  placeholder="Passphrase"
                  value={readPassphrase}
                  onChange={(event) => setReadPassphrase(event.target.value)}
                />
                <button
                  className="btn-secondary"
                  onClick={async () => {
                    const decrypted = await api.journal.read(entry.id, readPassphrase);
                    setSelectedEntry(decrypted);
                  }}
                  type="button"
                >
                  Read
                </button>
              </div>
            </div>
          ))}
        </div>
      </aside>
    </div>
  );
}
