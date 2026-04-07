import { useEffect, useMemo, useState } from "react";
import { PlayCircle, Plus, Trash2, Zap } from "lucide-react";

import { api } from "../services/api";
import { RuleTemplate, UserRule } from "../types/api";

const fallbackTemplates: RuleTemplate[] = [
  {
    name: "If sleep < 5 hours -> reduce today's workload by 30%",
    trigger_module: "sleep",
    trigger_condition: { field: "sleep_hours", operator: "<", value: 5 },
    action_module: "scheduler",
    action_type: "reduce_workload",
    action_params: { reduction_percent: 30 },
  },
  {
    name: "If missed gym 3 days in a row -> send harder reminder",
    trigger_module: "fitness",
    trigger_condition: { field: "missed_gym_streak_days", operator: ">=", value: 3 },
    action_module: "messaging",
    action_type: "send_harder_reminder",
    action_params: {
      title: "Gym streak broken",
      message: "You missed 3 days. Time to reset momentum now.",
    },
  },
  {
    name: "If portfolio drops 10% -> disable trading alerts for 24h",
    trigger_module: "trading",
    trigger_condition: { field: "portfolio_drop_pct", operator: "<=", value: -10 },
    action_module: "trading",
    action_type: "disable_alerts_temporarily",
    action_params: { hours: 24 },
  },
  {
    name: "If mood < 40 for 4 days -> activate recovery mode",
    trigger_module: "journal",
    trigger_condition: { field: "low_mood_streak_days", operator: ">=", value: 4 },
    action_module: "scheduler",
    action_type: "activate_recovery_mode",
    action_params: { insert_recovery_block: true },
  },
  {
    name: "If exam in 7 days -> increase study blocks by 2 per day",
    trigger_module: "study",
    trigger_condition: { field: "upcoming_exams_7d", operator: ">=", value: 1 },
    action_module: "scheduler",
    action_type: "increase_study_blocks",
    action_params: { extra_blocks: 2 },
  },
  {
    name: "If habit streak > 7 days -> award bonus XP",
    trigger_module: "habits",
    trigger_condition: { field: "max_habit_streak", operator: ">", value: 7 },
    action_module: "gamification",
    action_type: "award_bonus_xp",
    action_params: { xp: 40 },
  },
];

export default function RulesPage() {
  const [rules, setRules] = useState<UserRule[]>([]);
  const [templates, setTemplates] = useState<RuleTemplate[]>([]);
  const [selectedTemplate, setSelectedTemplate] = useState(0);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [statusText, setStatusText] = useState("");

  const activeRules = useMemo(() => rules.filter((item) => item.is_active), [rules]);

  const load = async () => {
    setLoading(true);
    try {
      const [ruleRows, templateRows] = await Promise.all([
        api.rules.list(),
        api.rules.templates().catch(() => fallbackTemplates),
      ]);
      setRules(ruleRows);
      setTemplates(templateRows.length > 0 ? templateRows : fallbackTemplates);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void load();
  }, []);

  const onCreateFromTemplate = async () => {
    const template = templates[selectedTemplate];
    if (!template) {
      return;
    }
    setBusy(true);
    setStatusText("");
    try {
      await api.rules.create({
        ...template,
        is_active: true,
      });
      setStatusText("Rule created.");
      await load();
    } finally {
      setBusy(false);
    }
  };

  const onToggleRule = async (rule: UserRule, next: boolean) => {
    setBusy(true);
    try {
      const updated = await api.rules.put(rule.id, { is_active: next });
      setRules((previous) =>
        previous.map((item) => (item.id === rule.id ? { ...item, is_active: updated.is_active } : item)),
      );
    } finally {
      setBusy(false);
    }
  };

  const onDeleteRule = async (ruleId: string) => {
    setBusy(true);
    try {
      await api.rules.remove(ruleId);
      setRules((previous) => previous.filter((item) => item.id !== ruleId));
    } finally {
      setBusy(false);
    }
  };

  const onEvaluateNow = async () => {
    setBusy(true);
    try {
      const result = await api.rules.evaluateNow();
      setStatusText(
        `Evaluated ${result.evaluated} rules, matched ${result.matched}, executed ${result.executed}.`,
      );
      await load();
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="space-y-6">
      <header className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Rules Engine</h1>
          <p className="text-sm text-[rgb(var(--text-dim))]">
            Build automations that react to your sleep, mood, study, fitness, and trading signals.
          </p>
        </div>

        <button
          type="button"
          onClick={() => void onEvaluateNow()}
          disabled={busy}
          className="inline-flex items-center gap-2 rounded-xl bg-[rgb(var(--primary))] px-4 py-2 text-sm font-semibold text-white disabled:opacity-60"
        >
          <PlayCircle className="h-4 w-4" /> Evaluate Now
        </button>
      </header>

      <section className="card p-4">
        <h2 className="text-lg font-semibold">Template Picker</h2>
        <p className="mt-1 text-sm text-[rgb(var(--text-dim))]">
          Start with a pre-built automation and tweak it later.
        </p>

        <div className="mt-3 flex flex-col gap-3 md:flex-row md:items-center">
          <select
            value={selectedTemplate}
            onChange={(event) => setSelectedTemplate(Number(event.target.value))}
            className="w-full rounded-xl border border-[rgb(var(--border))] bg-[rgb(var(--bg-muted))] px-3 py-2 text-sm md:max-w-xl"
          >
            {templates.map((template, index) => (
              <option key={template.name} value={index}>
                {template.name}
              </option>
            ))}
          </select>

          <button
            type="button"
            onClick={() => void onCreateFromTemplate()}
            disabled={busy || templates.length === 0}
            className="inline-flex items-center justify-center gap-2 rounded-xl border border-[rgb(var(--border))] bg-[rgb(var(--bg-elevated))] px-4 py-2 text-sm font-medium disabled:opacity-60"
          >
            <Plus className="h-4 w-4" /> Add Template Rule
          </button>
        </div>
      </section>

      <section className="space-y-3">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold">Active Rules ({activeRules.length})</h2>
          {statusText ? <p className="text-xs text-[rgb(var(--text-dim))]">{statusText}</p> : null}
        </div>

        {loading ? (
          <div className="card p-5 text-sm text-[rgb(var(--text-dim))]">Loading rules...</div>
        ) : rules.length === 0 ? (
          <div className="card p-5 text-sm text-[rgb(var(--text-dim))]">
            No rules yet. Add one from the template picker to automate your operating system.
          </div>
        ) : (
          <div className="grid gap-3">
            {rules.map((rule) => (
              <article key={rule.id} className="card p-4">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <h3 className="text-sm font-semibold">{rule.name}</h3>
                    <p className="mt-1 text-xs text-[rgb(var(--text-dim))]">
                      Trigger: {rule.trigger_module} {"->"} Action: {rule.action_module}/{rule.action_type}
                    </p>
                    <p className="mt-1 text-xs text-[rgb(var(--text-dim))]">
                      Last triggered: {rule.last_triggered ? new Date(rule.last_triggered).toLocaleString() : "Never"}
                    </p>
                  </div>

                  <div className="flex items-center gap-2">
                    <label className="inline-flex cursor-pointer items-center gap-2 text-xs">
                      <input
                        type="checkbox"
                        checked={rule.is_active}
                        onChange={(event) => void onToggleRule(rule, event.target.checked)}
                      />
                      <span>{rule.is_active ? "Active" : "Paused"}</span>
                    </label>

                    <button
                      type="button"
                      onClick={() => void onDeleteRule(rule.id)}
                      className="rounded-lg border border-[rgb(var(--danger))]/40 p-1.5 text-[rgb(var(--danger))]"
                    >
                      <Trash2 className="h-4 w-4" />
                    </button>
                  </div>
                </div>

                <div className="mt-3 rounded-lg bg-[rgb(var(--bg-muted))] p-2 text-xs text-[rgb(var(--text-dim))]">
                  <Zap className="mr-1 inline h-3.5 w-3.5" />
                  {JSON.stringify(rule.trigger_condition)}
                </div>
              </article>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
