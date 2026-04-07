import { AlertTriangle, Bot, CheckCircle2, Clock3 } from "lucide-react";

import { AgentRecommendationLog, AgentStatus } from "../types/api";

type Props = {
  statuses: AgentStatus[];
  recommendations: AgentRecommendationLog[];
  loading: boolean;
};

function toneForStatus(status: string) {
  if (status === "critical") {
    return "text-[rgb(var(--danger))]";
  }
  if (status === "warning") {
    return "text-[rgb(var(--warning))]";
  }
  return "text-[rgb(var(--success))]";
}

export default function AgentsPanel({ statuses, recommendations, loading }: Props) {
  if (loading && statuses.length === 0) {
    return <section className="card p-4 text-sm text-[rgb(var(--text-dim))]">Loading agent statuses...</section>;
  }

  return (
    <section className="card p-4">
      <div className="mb-3 flex items-center justify-between">
        <h3 className="inline-flex items-center gap-2 text-sm font-semibold">
          <Bot className="h-4 w-4" /> Agents
        </h3>
        <span className="text-xs text-[rgb(var(--text-dim))]">Hourly orchestration</span>
      </div>

      <div className="space-y-2">
        {statuses.length === 0 ? (
          <p className="text-xs text-[rgb(var(--text-dim))]">No agent status available yet.</p>
        ) : (
          statuses.map((status) => {
            const recSummary =
              typeof status.last_recommendation?.summary === "string"
                ? status.last_recommendation.summary
                : "No active recommendation.";
            const actionType =
              typeof status.last_action?.action_type === "string"
                ? status.last_action.action_type
                : "none";

            return (
              <article key={status.id} className="rounded-xl bg-[rgb(var(--bg-muted))] p-3">
                <div className="flex items-center justify-between gap-2">
                  <p className="text-sm font-semibold capitalize">{status.agent_name} agent</p>
                  <span className={`text-xs font-semibold uppercase tracking-wide ${toneForStatus(status.status)}`}>
                    {status.status}
                  </span>
                </div>
                <p className="mt-1 text-xs text-[rgb(var(--text-dim))]">{status.description}</p>
                <p className="mt-2 text-sm">{recSummary}</p>
                <p className="mt-1 text-xs text-[rgb(var(--text-dim))]">Last action: {actionType}</p>
              </article>
            );
          })
        )}
      </div>

      <div className="mt-3 rounded-xl border border-[rgb(var(--border))] bg-[rgb(var(--bg-elevated))] p-2">
        <p className="text-xs font-semibold uppercase tracking-wide text-[rgb(var(--text-dim))]">Latest recommendation</p>
        {recommendations[0] ? (
          <p className="mt-1 text-sm">
            <AlertTriangle className="mr-1 inline h-3.5 w-3.5" />
            {typeof recommendations[0].recommendation?.summary === "string"
              ? recommendations[0].recommendation.summary
              : `${recommendations[0].agent_name} issued a ${recommendations[0].severity} recommendation.`}
          </p>
        ) : (
          <p className="mt-1 text-xs text-[rgb(var(--text-dim))]">
            <Clock3 className="mr-1 inline h-3.5 w-3.5" /> No recommendations yet.
          </p>
        )}
        {recommendations[0]?.status === "executed" ? (
          <p className="mt-1 text-xs text-[rgb(var(--success))]">
            <CheckCircle2 className="mr-1 inline h-3.5 w-3.5" /> Latest recommendation executed.
          </p>
        ) : null}
      </div>
    </section>
  );
}
