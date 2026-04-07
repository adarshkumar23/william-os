import { motion, useReducedMotion } from "framer-motion";
import { Brain, CheckCircle2, Plus } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { fadeInUp, reduceMotion, staggerContainer } from "../lib/animations";
import { api } from "../services/api";
import { Decision, DecisionAnalysis } from "../types/api";
import { AppCard, Badge, EmptyState, Modal, SectionHeader, SkeletonLoader, TimelineCard } from "../components/ui";

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
  const [analysisById, setAnalysisById] = useState<Record<string, DecisionAnalysis>>({});
  const [openCreate, setOpenCreate] = useState(false);
  const [loading, setLoading] = useState(true);

  const [draft, setDraft] = useState({
    title: "",
    decision_type: "life",
    optionsText: "Option A\nOption B",
    criteriaText: "Impact\nCost\nTime",
    deadline: "",
  });

  const shouldReduceMotion = useReducedMotion();
  const fadeMotion = reduceMotion(shouldReduceMotion, fadeInUp);

  const load = async () => {
    setLoading(true);
    const rows = await api.decisions.list({ limit: 100, offset: 0 });
    setDecisions(rows);
    setLoading(false);
  };

  useEffect(() => {
    void load();
  }, []);

  const activeDecision = useMemo(() => decisions.find((item) => item.status !== "completed") || null, [decisions]);

  const timeline = useMemo(
    () =>
      [...decisions]
        .sort((a, b) => String(b.created_at || "").localeCompare(String(a.created_at || "")))
        .map((decision) => ({
          id: decision.id,
          title: decision.title,
          time: String(decision.created_at || decision.deadline || "-").slice(0, 10),
          status: decision.status === "completed" ? "done" : decision.status === "in_progress" ? "active" : "pending",
          category: decision.decision_type,
          confidence: Number(decision.confidence_score || 0),
        })),
    [decisions],
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
    setDraft({ title: "", decision_type: "life", optionsText: "Option A\nOption B", criteriaText: "Impact\nCost\nTime", deadline: "" });
    await load();
  };

  const onAnalyze = async (id: string) => {
    const result = await api.decisions.analyze(id);
    setAnalysisById((prev) => ({ ...prev, [id]: result }));
  };

  return (
    <div className="space-y-6">
      <SectionHeader
        title="Decisions"
        subtitle="Weighted choices, confidence signals, and timeline clarity."
        action={
          <button
            type="button"
            onClick={() => setOpenCreate(true)}
            className="inline-flex items-center gap-2 rounded-button bg-accent px-4 py-2 text-sm font-semibold text-white"
          >
            <Plus className="h-4 w-4" /> New Decision
          </button>
        }
      />

      {loading ? (
        <SkeletonLoader variant="card" />
      ) : decisions.length === 0 ? (
        <EmptyState
          icon={<Brain className="h-6 w-6" />}
          title="No decisions logged"
          description="Capture your first decision to activate scoring and timeline insights."
          action={
            <button
              type="button"
              onClick={() => setOpenCreate(true)}
              className="rounded-button bg-accent px-4 py-2 text-sm font-semibold text-white"
            >
              Create Decision
            </button>
          }
        />
      ) : (
        <motion.section variants={staggerContainer} initial="initial" animate="animate" className="grid gap-4 lg:grid-cols-5">
          <motion.div variants={fadeMotion} className="lg:col-span-3">
            <AppCard>
              <p className="section-label">Decision Timeline</p>
              <div className="mt-4 space-y-2">
                {timeline.map((item) => (
                  <div key={item.id} className="rounded-lg border border-border bg-surface-raised p-2">
                    <TimelineCard
                      time={item.time}
                      title={item.title}
                      category={item.category}
                      status={item.status as "pending" | "active" | "done"}
                      duration={`Confidence ${item.confidence}`}
                    />
                  </div>
                ))}
              </div>
            </AppCard>
          </motion.div>

          <motion.div variants={fadeMotion} className="lg:col-span-2">
            <AppCard>
              <p className="section-label">Active Decision</p>
              {activeDecision ? (
                <div className="mt-3 space-y-3">
                  <div className="flex items-start justify-between">
                    <div>
                      <h3 className="text-base font-semibold text-text-primary">{activeDecision.title}</h3>
                      <p className="meta-copy mt-1">Created: {String(activeDecision.created_at || activeDecision.deadline || "-").slice(0, 10)}</p>
                    </div>
                    <Badge label={activeDecision.status} variant={activeDecision.status === "completed" ? "success" : "accent"} />
                  </div>

                  <button
                    type="button"
                    onClick={() => void onAnalyze(activeDecision.id)}
                    className="inline-flex items-center gap-1 rounded-button border border-border px-3 py-1.5 text-xs"
                  >
                    <Brain className="h-3.5 w-3.5" /> Analyze
                  </button>

                  <div className="rounded-lg bg-surface-raised p-3">
                    <p className="meta-copy">Confidence</p>
                    <div className="group mt-2 h-2 rounded-full bg-border">
                      <div
                        className="h-2 rounded-full bg-accent transition-all duration-500 group-hover:brightness-125"
                        style={{ width: `${Math.max(0, Math.min(100, Number(activeDecision.confidence_score || 0) * 10))}%` }}
                      />
                    </div>
                  </div>

                  {analysisById[activeDecision.id] ? (
                    <div className="rounded-lg bg-surface-raised p-3 text-sm">
                      <p className="font-medium text-text-primary">Recommendation: {analysisById[activeDecision.id].recommendation}</p>
                      <p className="meta-copy mt-2">{analysisById[activeDecision.id].reasoning}</p>
                    </div>
                  ) : null}

                  <div className="flex gap-2">
                    <button
                      type="button"
                      className="rounded-button bg-accent px-3 py-1.5 text-xs font-semibold text-white"
                      onClick={() =>
                        void api.decisions
                          .choose(activeDecision.id, { chosen_option: String((activeDecision.options[0] || {}).name || "") })
                          .then(load)
                      }
                    >
                      Select Top Option
                    </button>
                    <button
                      type="button"
                      className="inline-flex items-center gap-1 rounded-button border border-border px-3 py-1.5 text-xs"
                      onClick={() =>
                        void api.decisions
                          .outcome(activeDecision.id, { outcome_notes: "Decision completed", outcome_rating: 7 })
                          .then(load)
                      }
                    >
                      <CheckCircle2 className="h-3.5 w-3.5" /> Mark Completed
                    </button>
                  </div>
                </div>
              ) : (
                <p className="body-copy mt-3">No active decision found.</p>
              )}
            </AppCard>
          </motion.div>
        </motion.section>
      )}

      <Modal isOpen={openCreate} onClose={() => setOpenCreate(false)} title="Create Decision" size="md">
        <div className="grid gap-3">
          <input
            value={draft.title}
            onChange={(event) => setDraft((prev) => ({ ...prev, title: event.target.value }))}
            placeholder="Title"
            className="rounded-input border border-border bg-surface-raised px-3 py-2 text-sm"
          />
          <input
            value={draft.decision_type}
            onChange={(event) => setDraft((prev) => ({ ...prev, decision_type: event.target.value }))}
            placeholder="Type"
            className="rounded-input border border-border bg-surface-raised px-3 py-2 text-sm"
          />
          <textarea
            rows={4}
            value={draft.optionsText}
            onChange={(event) => setDraft((prev) => ({ ...prev, optionsText: event.target.value }))}
            placeholder="Options (one per line)"
            className="rounded-input border border-border bg-surface-raised px-3 py-2 text-sm"
          />
          <textarea
            rows={4}
            value={draft.criteriaText}
            onChange={(event) => setDraft((prev) => ({ ...prev, criteriaText: event.target.value }))}
            placeholder="Criteria (one per line)"
            className="rounded-input border border-border bg-surface-raised px-3 py-2 text-sm"
          />
          <input
            type="datetime-local"
            value={draft.deadline}
            onChange={(event) => setDraft((prev) => ({ ...prev, deadline: event.target.value }))}
            className="rounded-input border border-border bg-surface-raised px-3 py-2 text-sm"
          />
        </div>

        <div className="mt-4 flex justify-end gap-2">
          <button
            type="button"
            onClick={() => setOpenCreate(false)}
            className="rounded-button border border-border px-4 py-2 text-sm"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={() => void onCreate()}
            className="rounded-button bg-accent px-4 py-2 text-sm font-semibold text-white"
          >
            Save
          </button>
        </div>
      </Modal>
    </div>
  );
}
