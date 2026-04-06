import { useEffect, useMemo, useState } from "react";
import { Brain, CheckCircle2, Plus } from "lucide-react";

import Modal from "../components/Modal";
import { api } from "../services/api";
import { Decision, DecisionAnalysis } from "../types/api";

function normalizeOptions(raw: string) {
  return raw
    .split("\n")
    .map((item) => item.trim())
    .filter(Boolean)
    .map((item) => ({ name: item, description: "" }));
}

function normalizeCriteria(raw: string) {
  return raw
    .split("\n")
    .map((item) => item.trim())
    .filter(Boolean)
    .map((item) => ({ name: item, weight: 5 }));
}

export default function DecisionsPage() {
  const [decisions, setDecisions] = useState<Decision[]>([]);
  const [stats, setStats] = useState<Record<string, unknown> | null>(null);
  const [analysisById, setAnalysisById] = useState<Record<string, DecisionAnalysis>>({});
  const [openCreate, setOpenCreate] = useState(false);

  const [draft, setDraft] = useState({
    title: "",
    decision_type: "life",
    optionsText: "Option A\nOption B",
    criteriaText: "Impact\nCost\nTime",
    deadline: "",
  });

  const load = async () => {
    const [rows, decisionStats] = await Promise.all([api.decisions.list({ limit: 100, offset: 0 }), api.decisions.stats().catch(() => null)]);
    setDecisions(rows);
    setStats(decisionStats);
  };

  useEffect(() => {
    void load();
  }, []);

  const activeDecisions = decisions.filter((item) => item.status !== "completed");
  const completedDecisions = decisions.filter((item) => item.status === "completed");

  const timeline = useMemo(
    () =>
      completedDecisions.map((decision) => ({
        title: decision.title,
        subtitle: `Outcome rating: ${decision.outcome_rating ?? "N/A"}`,
        at: decision.deadline || "No deadline",
        state: "done" as const,
      })),
    [completedDecisions],
  );

  const onCreate = async () => {
    await api.decisions.create({
      title: draft.title,
      decision_type: draft.decision_type,
      options: normalizeOptions(draft.optionsText),
      criteria: normalizeCriteria(draft.criteriaText),
      deadline: draft.deadline || null,
    });
    setOpenCreate(false);
    setDraft({
      title: "",
      decision_type: "life",
      optionsText: "Option A\nOption B",
      criteriaText: "Impact\nCost\nTime",
      deadline: "",
    });
    await load();
  };

  const onAnalyze = async (id: string) => {
    const result = await api.decisions.analyze(id);
    setAnalysisById((prev) => ({ ...prev, [id]: result }));
  };

  return (
    <div className="space-y-6">
      <header className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Decision Engine</h1>
          <p className="text-sm text-[rgb(var(--text-dim))]">Structured choices with weighted reasoning.</p>
        </div>
        <button
          type="button"
          onClick={() => setOpenCreate(true)}
          className="inline-flex items-center gap-2 rounded-xl bg-[rgb(var(--primary))] px-4 py-2 text-sm font-semibold text-white"
        >
          <Plus className="h-4 w-4" /> New decision
        </button>
      </header>

      <section className="grid gap-3 sm:grid-cols-3">
        <article className="card p-4">
          <p className="text-sm text-[rgb(var(--text-dim))]">Total decisions</p>
          <p className="mt-1 data-font text-3xl font-bold">{String(stats?.total_decisions ?? decisions.length)}</p>
        </article>
        <article className="card p-4">
          <p className="text-sm text-[rgb(var(--text-dim))]">Completed</p>
          <p className="mt-1 data-font text-3xl font-bold">{String(stats?.completed_decisions ?? completedDecisions.length)}</p>
        </article>
        <article className="card p-4">
          <p className="text-sm text-[rgb(var(--text-dim))]">Avg confidence</p>
          <p className="mt-1 data-font text-3xl font-bold">{String(stats?.avg_confidence ?? "--")}</p>
        </article>
      </section>

      <section className="grid gap-4 lg:grid-cols-2">
        <div className="space-y-3">
          <h2 className="text-lg font-semibold">Active decisions</h2>
          {activeDecisions.map((decision) => {
            const analysis = analysisById[decision.id];
            return (
              <article key={decision.id} className="card p-4">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <p className="font-semibold">{decision.title}</p>
                    <p className="text-xs text-[rgb(var(--text-dim))]">Type: {decision.decision_type}</p>
                  </div>
                  <button
                    type="button"
                    onClick={() => void onAnalyze(decision.id)}
                    className="inline-flex items-center gap-1 rounded-lg border border-[rgb(var(--border))] px-2 py-1 text-xs"
                  >
                    <Brain className="h-3.5 w-3.5" /> Analyze
                  </button>
                </div>

                {analysis ? (
                  <div className="mt-3 rounded-xl bg-[rgb(var(--bg-muted))] p-3 text-xs">
                    <p className="font-semibold">Recommendation: {analysis.recommendation}</p>
                    <p className="mt-1 text-[rgb(var(--text-dim))]">{analysis.reasoning}</p>
                    <p className="mt-1 text-[rgb(var(--text-dim))]">Confidence: {analysis.confidence}</p>
                  </div>
                ) : null}

                <div className="mt-3 flex gap-2">
                  <button
                    type="button"
                    className="rounded-lg bg-[rgb(var(--primary))] px-2 py-1 text-xs font-semibold text-white"
                    onClick={() =>
                      void api.decisions
                        .choose(decision.id, { chosen_option: String((decision.options[0] || {}).name || "") })
                        .then(load)
                    }
                  >
                    Select top option
                  </button>
                  <button
                    type="button"
                    className="rounded-lg border border-[rgb(var(--border))] px-2 py-1 text-xs"
                    onClick={() =>
                      void api.decisions
                        .outcome(decision.id, { outcome_notes: "Decision completed", outcome_rating: 7 })
                        .then(load)
                    }
                  >
                    Mark completed
                  </button>
                </div>
              </article>
            );
          })}
          {activeDecisions.length === 0 ? <div className="card p-6 text-sm text-[rgb(var(--text-dim))]">No active decisions.</div> : null}
        </div>

        <div className="space-y-3">
          <h2 className="text-lg font-semibold">Decision timeline</h2>
          <div className="space-y-2">
            {timeline.map((item, index) => (
              <article key={`${item.title}-${index}`} className="card p-4">
                <p className="text-xs uppercase tracking-widest text-[rgb(var(--text-dim))]">{item.at}</p>
                <h3 className="mt-1 text-sm font-semibold">{item.title}</h3>
                <p className="mt-1 text-xs text-[rgb(var(--text-dim))]">{item.subtitle}</p>
              </article>
            ))}
            {timeline.length === 0 ? <div className="card p-6 text-sm text-[rgb(var(--text-dim))]">No completed decisions yet.</div> : null}
          </div>
        </div>
      </section>

      <Modal
        open={openCreate}
        onClose={() => setOpenCreate(false)}
        title="Create decision"
        footer={
          <div className="flex justify-end gap-2">
            <button
              type="button"
              onClick={() => setOpenCreate(false)}
              className="rounded-lg border border-[rgb(var(--border))] px-3 py-2 text-sm"
            >
              Cancel
            </button>
            <button
              type="button"
              onClick={() => void onCreate()}
              className="inline-flex items-center gap-2 rounded-lg bg-[rgb(var(--primary))] px-3 py-2 text-sm font-semibold text-white"
            >
              <CheckCircle2 className="h-4 w-4" /> Save
            </button>
          </div>
        }
      >
        <div className="grid gap-3">
          <label className="space-y-1">
            <span className="text-sm font-medium">Title</span>
            <input
              value={draft.title}
              onChange={(event) => setDraft((prev) => ({ ...prev, title: event.target.value }))}
              className="w-full rounded-xl border border-[rgb(var(--border))] bg-[rgb(var(--bg-muted))] px-3 py-2"
            />
          </label>
          <label className="space-y-1">
            <span className="text-sm font-medium">Type</span>
            <input
              value={draft.decision_type}
              onChange={(event) => setDraft((prev) => ({ ...prev, decision_type: event.target.value }))}
              className="w-full rounded-xl border border-[rgb(var(--border))] bg-[rgb(var(--bg-muted))] px-3 py-2"
            />
          </label>
          <label className="space-y-1">
            <span className="text-sm font-medium">Options (one per line)</span>
            <textarea
              rows={4}
              value={draft.optionsText}
              onChange={(event) => setDraft((prev) => ({ ...prev, optionsText: event.target.value }))}
              className="w-full rounded-xl border border-[rgb(var(--border))] bg-[rgb(var(--bg-muted))] px-3 py-2"
            />
          </label>
          <label className="space-y-1">
            <span className="text-sm font-medium">Criteria (one per line)</span>
            <textarea
              rows={4}
              value={draft.criteriaText}
              onChange={(event) => setDraft((prev) => ({ ...prev, criteriaText: event.target.value }))}
              className="w-full rounded-xl border border-[rgb(var(--border))] bg-[rgb(var(--bg-muted))] px-3 py-2"
            />
          </label>
          <label className="space-y-1">
            <span className="text-sm font-medium">Deadline</span>
            <input
              type="datetime-local"
              value={draft.deadline}
              onChange={(event) => setDraft((prev) => ({ ...prev, deadline: event.target.value }))}
              className="w-full rounded-xl border border-[rgb(var(--border))] bg-[rgb(var(--bg-muted))] px-3 py-2"
            />
          </label>
        </div>
      </Modal>
    </div>
  );
}
