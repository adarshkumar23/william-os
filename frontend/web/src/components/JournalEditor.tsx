import { FormEvent, useState } from "react";

export type JournalDraft = {
  content: string;
  passphrase: string;
  mood?: string;
  tags: string[];
};

export default function JournalEditor({
  onSubmit,
}: {
  onSubmit: (draft: JournalDraft) => Promise<void>;
}) {
  const [content, setContent] = useState("");
  const [passphrase, setPassphrase] = useState("");
  const [mood, setMood] = useState("okay");
  const [tags, setTags] = useState("reflection");

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();
    await onSubmit({
      content,
      passphrase,
      mood,
      tags: tags.split(",").map((item) => item.trim()).filter(Boolean),
    });
    setContent("");
  };

  return (
    <form className="panel space-y-3 p-4" onSubmit={handleSubmit}>
      <h3 className="font-display text-lg font-bold">New Journal Entry</h3>
      <textarea
        className="h-36 w-full rounded-xl border border-slate-300 bg-white/80 p-3 dark:border-slate-700 dark:bg-slate-900"
        placeholder="How did today feel?"
        value={content}
        onChange={(event) => setContent(event.target.value)}
      />
      <div className="grid gap-3 md:grid-cols-3">
        <input
          className="rounded-xl border border-slate-300 bg-white/80 p-2 dark:border-slate-700 dark:bg-slate-900"
          type="password"
          placeholder="Passphrase"
          value={passphrase}
          onChange={(event) => setPassphrase(event.target.value)}
        />
        <select
          className="rounded-xl border border-slate-300 bg-white/80 p-2 dark:border-slate-700 dark:bg-slate-900"
          value={mood}
          onChange={(event) => setMood(event.target.value)}
        >
          <option value="great">Great</option>
          <option value="good">Good</option>
          <option value="okay">Okay</option>
          <option value="low">Low</option>
          <option value="bad">Bad</option>
        </select>
        <input
          className="rounded-xl border border-slate-300 bg-white/80 p-2 dark:border-slate-700 dark:bg-slate-900"
          placeholder="tags,separated,by,comma"
          value={tags}
          onChange={(event) => setTags(event.target.value)}
        />
      </div>
      <button className="btn-primary" type="submit">
        Save Entry
      </button>
    </form>
  );
}
