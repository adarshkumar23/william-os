import {
  AlertTriangle,
  Briefcase,
  Code2,
  FolderGit2,
  TrendingUp,
  Users,
  Zap,
} from "lucide-react";
import { useNavigate } from "react-router-dom";
import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import ProgressRing from "../../components/ui/ProgressRing";
import { useCareerDashboard } from "../../hooks/useCareerDashboard";

function StatItem({ label, value, icon: Icon }: { label: string; value: number | string; icon: React.ComponentType<{ className?: string }> }) {
  return (
    <div className="flex flex-col items-center gap-1 rounded-xl border border-border bg-surface p-4 text-center">
      <Icon className="h-5 w-5 text-indigo-400" />
      <p className="text-2xl font-bold text-text-primary tabular-nums">{value}</p>
      <p className="meta-copy">{label}</p>
    </div>
  );
}

export default function CareerDashboardPage() {
  const { data, loading, error } = useCareerDashboard();
  const navigate = useNavigate();

  if (loading) {
    return (
      <div className="flex h-64 items-center justify-center">
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-indigo-500 border-t-transparent" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="rounded-xl border border-red-500/20 bg-red-500/10 p-6 text-red-400">
        {error}
      </div>
    );
  }

  const score = data?.score ?? { overall: 0, components: {}, snapshot_date: "" };
  const history = data?.score_history ?? [];
  const stats = data?.stats ?? { problems_solved: 0, deployed_projects: 0, active_applications: 0, contacts: 0, cf_rating: 0 };
  const pipelinePreview = data?.pipeline_preview ?? {};
  const recentOpps = data?.recent_opportunities ?? [];
  const warnings = data?.warnings ?? [];

  const appliedCount = (pipelinePreview["applied"] ?? []).length;
  const interviewCount = (pipelinePreview["interview"] ?? []).length;
  const offerCount = (pipelinePreview["offer"] ?? []).length;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-text-primary">Career OS</h1>
        <p className="meta-copy mt-1">Track your job search, skill growth, and network.</p>
      </div>

      {warnings.length > 0 && (
        <div className="space-y-2">
          {warnings.map((w, i) => (
            <div key={i} className="flex items-center gap-2 rounded-lg border border-amber-400/20 bg-amber-400/10 px-4 py-2 text-sm text-amber-300">
              <AlertTriangle className="h-4 w-4 shrink-0" />
              {w}
            </div>
          ))}
        </div>
      )}

      {/* Row 1: Score + Momentum */}
      <div className="grid grid-cols-3 gap-4">
        <div className="col-span-2 rounded-xl border border-border bg-surface p-6">
          <div className="flex items-start gap-6">
            <ProgressRing
              value={score.overall}
              size="lg"
              color="rgb(99,102,241)"
              label="Career Score"
              sublabel={`/ 100`}
            />
            <div className="flex-1 space-y-3">
              <h2 className="font-semibold text-text-primary">Score Breakdown</h2>
              {[
                { label: "DSA", key: "dsa", max: 25 },
                { label: "Projects", key: "projects", max: 25 },
                { label: "Applications", key: "applications", max: 20 },
                { label: "Network", key: "network", max: 15 },
                { label: "Competitive", key: "cp", max: 15 },
              ].map(({ label, key, max }) => {
                const val = (score.components[key] as number) ?? 0;
                return (
                  <div key={key}>
                    <div className="mb-1 flex justify-between text-xs">
                      <span className="text-text-secondary">{label}</span>
                      <span className="font-medium text-text-primary">{val}/{max}</span>
                    </div>
                    <div className="h-1.5 rounded-full bg-surface-raised">
                      <div
                        className="h-1.5 rounded-full bg-indigo-500 transition-all"
                        style={{ width: `${(val / max) * 100}%` }}
                      />
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </div>

        <div className="rounded-xl border border-border bg-surface p-4">
          <div className="mb-3 flex items-center gap-2">
            <TrendingUp className="h-4 w-4 text-indigo-400" />
            <h3 className="text-sm font-semibold text-text-primary">Momentum (7d)</h3>
          </div>
          {history.length > 1 ? (
            <ResponsiveContainer width="100%" height={140}>
              <AreaChart data={[...history].reverse()}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
                <XAxis dataKey="date" hide />
                <YAxis domain={[0, 100]} hide />
                <Tooltip
                  contentStyle={{ background: "var(--color-surface)", border: "1px solid var(--color-border)", borderRadius: 8 }}
                  labelStyle={{ color: "var(--color-text-secondary)" }}
                />
                <Area type="monotone" dataKey="score" stroke="rgb(99,102,241)" fill="rgba(99,102,241,0.15)" strokeWidth={2} />
              </AreaChart>
            </ResponsiveContainer>
          ) : (
            <p className="meta-copy mt-4 text-center">No history yet</p>
          )}
        </div>
      </div>

      {/* Row 2: Stats strip */}
      <div className="grid grid-cols-5 gap-3">
        <StatItem label="Problems Solved" value={stats.problems_solved} icon={Code2} />
        <StatItem label="Deployed Projects" value={stats.deployed_projects} icon={FolderGit2} />
        <StatItem label="Active Applications" value={stats.active_applications} icon={Briefcase} />
        <StatItem label="Contacts" value={stats.contacts} icon={Users} />
        <StatItem label="CF Rating" value={stats.cf_rating || "—"} icon={Zap} />
      </div>

      {/* Row 3: Pipeline preview + Opportunities */}
      <div className="grid grid-cols-3 gap-4">
        <div className="col-span-2 rounded-xl border border-border bg-surface p-4">
          <div className="mb-3 flex items-center justify-between">
            <h3 className="font-semibold text-text-primary">Applications Pipeline</h3>
            <button
              onClick={() => navigate("/career/applications")}
              className="text-xs text-indigo-400 hover:text-indigo-300"
            >
              View all →
            </button>
          </div>
          <div className="flex items-center gap-2 text-sm">
            {["researching", "applied", "oa", "interview", "offer"].map((stage, i, arr) => {
              const count = (pipelinePreview[stage] ?? []).length;
              return (
                <div key={stage} className="flex items-center gap-2">
                  <div className="rounded-lg border border-border bg-surface-raised px-3 py-2 text-center">
                    <p className="text-xl font-bold text-text-primary">{count}</p>
                    <p className="meta-copy capitalize">{stage}</p>
                  </div>
                  {i < arr.length - 1 && <span className="text-text-secondary">→</span>}
                </div>
              );
            })}
          </div>
          {appliedCount + interviewCount + offerCount > 0 && (
            <div className="mt-3 space-y-1">
              {[...(pipelinePreview["interview"] ?? []), ...(pipelinePreview["applied"] ?? [])].slice(0, 3).map((app) => (
                <div key={app.id} className="flex items-center justify-between rounded-lg bg-surface-raised px-3 py-2 text-sm">
                  <span className="font-medium text-text-primary">{app.company}</span>
                  <span className="meta-copy">{app.role}</span>
                  <span className="rounded-full bg-indigo-500/15 px-2 py-0.5 text-xs text-indigo-300 capitalize">{app.stage}</span>
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="rounded-xl border border-border bg-surface p-4">
          <div className="mb-3 flex items-center justify-between">
            <h3 className="font-semibold text-text-primary">Opportunities</h3>
            <button
              onClick={() => navigate("/career/opportunities")}
              className="text-xs text-indigo-400 hover:text-indigo-300"
            >
              View all →
            </button>
          </div>
          {recentOpps.length === 0 ? (
            <p className="meta-copy mt-4 text-center">No open opportunities</p>
          ) : (
            <div className="space-y-2">
              {recentOpps.map((opp) => {
                const deadline = opp.deadline ? new Date(opp.deadline) : null;
                const daysLeft = deadline ? Math.ceil((deadline.getTime() - Date.now()) / 86400000) : null;
                const countdownClass =
                  daysLeft === null ? "text-text-secondary"
                  : daysLeft > 7 ? "text-green-400"
                  : daysLeft > 3 ? "text-amber-400"
                  : daysLeft > 0 ? "text-red-400"
                  : "text-text-secondary line-through";
                return (
                  <div key={opp.id} className="rounded-lg bg-surface-raised p-2 text-sm">
                    <p className="font-medium text-text-primary truncate">{opp.title}</p>
                    <div className="mt-1 flex items-center justify-between">
                      <span className="rounded-full bg-surface px-2 py-0.5 text-xs text-text-secondary capitalize">{opp.kind}</span>
                      <span className={`text-xs ${countdownClass}`}>
                        {daysLeft === null ? "No deadline"
                          : daysLeft > 0 ? `${daysLeft}d left`
                          : "Overdue"}
                      </span>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
