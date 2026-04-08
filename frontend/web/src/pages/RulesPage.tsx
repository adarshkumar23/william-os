import clsx from "clsx";
import { formatDistanceToNow } from "date-fns";
import { motion, useReducedMotion } from "framer-motion";
import {
  ArrowRight,
  Bot,
  Clock3,
  Pencil,
  PlayCircle,
  Plus,
  Sparkles,
  Trash2,
  TriangleAlert,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { api } from "../services/api";
import { RuleEvaluationLog, RuleTemplate, UserRule } from "../types/api";
import { AppCard, Badge, Modal, SkeletonLoader } from "../components/ui";

type TriggerModule =
  | "sleep"
  | "habits"
  | "fitness"
  | "energy"
  | "trading"
  | "study"
  | "medicine";
type ActionModule = "scheduler" | "notifications" | "habits" | "study" | "chat";
type OperatorKey = "lt" | "gt" | "eq" | "lte" | "gte";
type ParamType = "number" | "text";

type ActionParamDefinition = {
  key: string;
  label: string;
  type: ParamType;
  defaultValue: number | string;
  placeholder?: string;
};

type ActionDefinition = {
  value: string;
  label: string;
  params: ActionParamDefinition[];
};

type RuleBuilder = {
  name: string;
  triggerModule: TriggerModule;
  metric: string;
  operator: OperatorKey;
  value: number;
  actionModule: ActionModule;
  actionType: string;
  actionParams: Record<string, string | number>;
  isActive: boolean;
};

type RuleTemplateWithSummary = RuleTemplate & { summary: string };

const TRIGGER_MODULE_LABELS: Record<TriggerModule, string> = {
  sleep: "Sleep",
  habits: "Habits",
  fitness: "Fitness",
  energy: "Energy",
  trading: "Trading",
  study: "Study",
  medicine: "Medicine",
};

const TRIGGER_METRICS: Record<TriggerModule, string[]> = {
  sleep: ["duration_hours", "quality_score", "debt_hours"],
  habits: ["streak", "completion_rate", "missed_days"],
  fitness: ["steps", "calories", "workout_duration"],
  energy: ["energy_score", "peak_hours", "low_hours"],
  trading: ["profit_loss", "win_rate", "daily_loss"],
  study: ["sessions_completed", "accuracy", "revision_due"],
  medicine: ["adherence_rate", "missed_doses"],
};

const OPERATOR_OPTIONS: Array<{ value: OperatorKey; label: string; symbol: string }> = [
  { value: "lt", label: "is less than", symbol: "<" },
  { value: "gt", label: "is greater than", symbol: ">" },
  { value: "eq", label: "equals", symbol: "==" },
  { value: "lte", label: "is less than or equal", symbol: "<=" },
  { value: "gte", label: "is greater than or equal", symbol: ">=" },
];

const ACTION_OPTIONS: Record<ActionModule, ActionDefinition[]> = {
  scheduler: [
    {
      value: "reduce_workload",
      label: "Reduce workload",
      params: [{ key: "reduce_by", label: "Reduce by (hours)", type: "number", defaultValue: 2 }],
    },
    {
      value: "add_rest_block",
      label: "Add rest block",
      params: [
        { key: "duration_minutes", label: "Rest duration (minutes)", type: "number", defaultValue: 60 },
      ],
    },
    {
      value: "reschedule_tasks",
      label: "Reschedule tasks",
      params: [{ key: "shift_by_hours", label: "Shift by (hours)", type: "number", defaultValue: 1 }],
    },
  ],
  notifications: [
    {
      value: "send_alert",
      label: "Send alert",
      params: [{ key: "message", label: "Alert message", type: "text", defaultValue: "Rest today" }],
    },
    {
      value: "send_telegram",
      label: "Send Telegram",
      params: [
        {
          key: "message",
          label: "Telegram message",
          type: "text",
          defaultValue: "Quick reminder from William.",
        },
      ],
    },
    {
      value: "morning_warning",
      label: "Morning warning",
      params: [
        {
          key: "message",
          label: "Warning message",
          type: "text",
          defaultValue: "Energy is low. Keep today lighter.",
        },
      ],
    },
  ],
  habits: [
    {
      value: "skip_habit",
      label: "Skip habit",
      params: [{ key: "habit_name", label: "Habit name", type: "text", defaultValue: "Workout" }],
    },
    {
      value: "mark_rest_day",
      label: "Mark rest day",
      params: [{ key: "message", label: "Reason", type: "text", defaultValue: "Recovery day" }],
    },
    {
      value: "reduce_target",
      label: "Reduce target",
      params: [{ key: "reduce_by", label: "Reduce by", type: "number", defaultValue: 1 }],
    },
  ],
  study: [
    {
      value: "pause_sessions",
      label: "Pause sessions",
      params: [{ key: "hours", label: "Pause for (hours)", type: "number", defaultValue: 12 }],
    },
    {
      value: "extend_deadline",
      label: "Extend deadline",
      params: [{ key: "days", label: "Extend by (days)", type: "number", defaultValue: 1 }],
    },
  ],
  chat: [
    {
      value: "send_william_message",
      label: "Send William message",
      params: [
        {
          key: "message",
          label: "Message",
          type: "text",
          defaultValue: "Take a short break and recover.",
        },
      ],
    },
  ],
};

const TRIGGER_BADGE_COLOR: Record<string, string> = {
  sleep: "bg-blue-500/20 text-blue-300",
  habits: "bg-emerald-500/20 text-emerald-300",
  fitness: "bg-orange-500/20 text-orange-300",
  energy: "bg-yellow-500/20 text-yellow-300",
  trading: "bg-purple-500/20 text-purple-300",
  study: "bg-indigo-500/20 text-indigo-300",
  medicine: "bg-pink-500/20 text-pink-300",
};

const FALLBACK_TEMPLATES: RuleTemplateWithSummary[] = [
  {
    name: "Recovery Mode",
    trigger_module: "sleep",
    trigger_condition: { metric: "duration_hours", field: "duration_hours", operator: "<", value: 5 },
    action_module: "scheduler",
    action_type: "reduce_workload",
    action_params: { reduce_by: 2 },
    summary: "If sleep < 5h → reduce workload by 2 hours",
  },
  {
    name: "Streak Saver",
    trigger_module: "habits",
    trigger_condition: { metric: "streak", field: "streak", operator: ">", value: 7 },
    action_module: "notifications",
    action_type: "send_alert",
    action_params: { message: "Great streak. Keep momentum going." },
    summary: "If habit streak > 7 days → send motivational alert",
  },
  {
    name: "Energy Crash",
    trigger_module: "energy",
    trigger_condition: { metric: "energy_score", field: "energy_score", operator: "<", value: 30 },
    action_module: "scheduler",
    action_type: "add_rest_block",
    action_params: { duration_minutes: 60 },
    summary: "If energy score < 30 → add a rest block",
  },
  {
    name: "Trading Discipline",
    trigger_module: "trading",
    trigger_condition: { metric: "daily_loss", field: "daily_loss", operator: ">", value: 5 },
    action_module: "notifications",
    action_type: "send_alert",
    action_params: { message: "Daily loss exceeded threshold. Pause and review risk." },
    summary: "If daily loss > threshold → send warning alert",
  },
  {
    name: "Study Burnout",
    trigger_module: "study",
    trigger_condition: { metric: "sessions_completed", field: "sessions_completed", operator: ">", value: 4 },
    action_module: "study",
    action_type: "pause_sessions",
    action_params: { hours: 8 },
    summary: "If study sessions > 4 → pause sessions for the day",
  },
  {
    name: "Medicine Alert",
    trigger_module: "medicine",
    trigger_condition: { metric: "adherence_rate", field: "adherence_rate", operator: "<", value: 80 },
    action_module: "notifications",
    action_type: "send_telegram",
    action_params: { message: "Medication adherence dipped below 80%." },
    summary: "If adherence rate < 80% → send Telegram reminder",
  },
  {
    name: "Fitness Streak",
    trigger_module: "fitness",
    trigger_condition: { metric: "steps", field: "steps", operator: "<", value: 3000 },
    action_module: "notifications",
    action_type: "send_alert",
    action_params: { message: "Steps are low today. Quick walk now?" },
    summary: "If steps < 3000 → send walk reminder",
  },
  {
    name: "Deep Work Trigger",
    trigger_module: "energy",
    trigger_condition: { metric: "energy_score", field: "energy_score", operator: ">", value: 80 },
    action_module: "scheduler",
    action_type: "reschedule_tasks",
    action_params: { shift_by_hours: 1 },
    summary: "If energy score > 80 → schedule a focus block",
  },
];

const suggestedTemplate = FALLBACK_TEMPLATES[0];

const operatorToSymbol = (operator: OperatorKey): string => {
  return OPERATOR_OPTIONS.find((item) => item.value === operator)?.symbol ?? "==";
};

const symbolToOperator = (symbol: string): OperatorKey => {
  const normalized = symbol.trim();
  if (normalized === "<") return "lt";
  if (normalized === ">") return "gt";
  if (normalized === "<=") return "lte";
  if (normalized === ">=") return "gte";
  return "eq";
};

const normalizeActionModule = (value: unknown): ActionModule => {
  const raw = String(value || "").toLowerCase();
  if (raw === "notifications" || raw === "messaging") return "notifications";
  if (raw === "habits") return "habits";
  if (raw === "study") return "study";
  if (raw === "chat") return "chat";
  return "scheduler";
};

const defaultActionForModule = (module: ActionModule): ActionDefinition => {
  return ACTION_OPTIONS[module][0];
};

const findActionDefinition = (module: ActionModule, actionType: string): ActionDefinition => {
  return ACTION_OPTIONS[module].find((item) => item.value === actionType) || defaultActionForModule(module);
};

const buildDefaultActionParams = (module: ActionModule, actionType: string) => {
  const definition = findActionDefinition(module, actionType);
  const values: Record<string, string | number> = {};
  for (const param of definition.params) {
    values[param.key] = param.defaultValue;
  }
  return values;
};

const createBlankBuilder = (): RuleBuilder => {
  const triggerModule: TriggerModule = "sleep";
  const actionModule: ActionModule = "scheduler";
  const actionType = defaultActionForModule(actionModule).value;
  return {
    name: "",
    triggerModule,
    metric: TRIGGER_METRICS[triggerModule][0],
    operator: "lt",
    value: 5,
    actionModule,
    actionType,
    actionParams: buildDefaultActionParams(actionModule, actionType),
    isActive: true,
  };
};

const humanizeKey = (value: string): string => {
  return value
    .replace(/_/g, " ")
    .replace(/\b\w/g, (char) => char.toUpperCase());
};

const metricUnit = (metric: string): string => {
  if (metric.includes("hours")) return "h";
  if (metric.includes("rate") || metric.includes("accuracy")) return "%";
  return "";
};

const summarizeCondition = (condition: Record<string, unknown>): string => {
  const metric = String(condition.metric || condition.field || "metric");
  const operator = symbolToOperator(String(condition.operator || "=="));
  const symbol = operatorToSymbol(operator);
  const rawValue = condition.value;
  const numeric = typeof rawValue === "number" ? rawValue : Number(rawValue || 0);
  const value = Number.isFinite(numeric) ? numeric : String(rawValue || "-");
  return `${humanizeKey(metric)} ${symbol} ${value}${metricUnit(metric)}`;
};

const summarizeAction = (rule: { action_module: string; action_type: string }): string => {
  const module = normalizeActionModule(rule.action_module);
  const definition = findActionDefinition(module, rule.action_type);
  return `${humanizeKey(module)} • ${definition.label}`;
};

const relativeTriggered = (value?: string | null): string => {
  if (!value) return "Never";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return "Never";
  return formatDistanceToNow(parsed, { addSuffix: true });
};

export default function RulesPage() {
  const shouldReduceMotion = useReducedMotion();
  const [rules, setRules] = useState<UserRule[]>([]);
  const [templates, setTemplates] = useState<RuleTemplateWithSummary[]>([]);
  const [executionLogs, setExecutionLogs] = useState<RuleEvaluationLog[]>([]);

  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [runningNow, setRunningNow] = useState(false);
  const [error, setError] = useState("");
  const [statusText, setStatusText] = useState("");

  const [modalOpen, setModalOpen] = useState(false);
  const [modalStep, setModalStep] = useState<1 | 2 | 3>(1);
  const [editingRuleId, setEditingRuleId] = useState<string | null>(null);
  const [nameTouched, setNameTouched] = useState(false);
  const [builder, setBuilder] = useState<RuleBuilder>(createBlankBuilder);

  const activeCount = useMemo(() => rules.filter((rule) => rule.is_active).length, [rules]);

  const ruleNameById = useMemo(() => {
    return new Map(rules.map((rule) => [rule.id, rule.name]));
  }, [rules]);

  const autoName = useMemo(() => {
    const moduleLabel = TRIGGER_MODULE_LABELS[builder.triggerModule];
    const symbol = operatorToSymbol(builder.operator);
    const action = findActionDefinition(builder.actionModule, builder.actionType).label;
    return `If ${moduleLabel.toLowerCase()} ${symbol} ${builder.value}${metricUnit(builder.metric)} -> ${action.toLowerCase()}`;
  }, [builder.actionModule, builder.actionType, builder.metric, builder.operator, builder.triggerModule, builder.value]);

  useEffect(() => {
    if (!modalOpen || nameTouched) {
      return;
    }
    setBuilder((previous) => ({ ...previous, name: autoName }));
  }, [autoName, modalOpen, nameTouched]);

  const load = async () => {
    setLoading(true);
    setError("");
    try {
      const [ruleRows, templateRows] = await Promise.all([
        api.rules.listRules(),
        api.rules.getTemplates().catch(() => []),
      ]);
      setRules(ruleRows);

      const mappedTemplates = (templateRows || []).map((template) => ({
        ...template,
        summary: `If ${summarizeCondition(template.trigger_condition || {})} -> ${summarizeAction({
          action_module: template.action_module,
          action_type: template.action_type,
        })}`,
      }));
      setTemplates(mappedTemplates.length ? mappedTemplates : FALLBACK_TEMPLATES);
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : "Failed to load rules.");
      setTemplates(FALLBACK_TEMPLATES);
      setRules([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void load();
  }, []);

  const resetBuilder = () => {
    setBuilder(createBlankBuilder());
    setModalStep(1);
    setEditingRuleId(null);
    setNameTouched(false);
  };

  const openNewRule = () => {
    resetBuilder();
    setModalOpen(true);
  };

  const openFromTemplate = (template: RuleTemplate) => {
    const condition = template.trigger_condition || {};
    const triggerModule = String(template.trigger_module || "sleep") as TriggerModule;
    const safeTriggerModule = TRIGGER_METRICS[triggerModule] ? triggerModule : "sleep";
    const actionModule = normalizeActionModule(template.action_module);
    const actionType = String(template.action_type || defaultActionForModule(actionModule).value);
    const metric = String(condition.metric || condition.field || TRIGGER_METRICS[safeTriggerModule][0]);
    const operator = symbolToOperator(String(condition.operator || "=="));
    const value = Number(condition.value || 0);

    const nextParams = {
      ...buildDefaultActionParams(actionModule, actionType),
      ...(template.action_params || {}),
    };

    setBuilder({
      name: template.name,
      triggerModule: safeTriggerModule,
      metric,
      operator,
      value: Number.isFinite(value) ? value : 0,
      actionModule,
      actionType,
      actionParams: nextParams as Record<string, string | number>,
      isActive: true,
    });
    setNameTouched(true);
    setEditingRuleId(null);
    setModalStep(1);
    setModalOpen(true);
  };

  const openEditRule = (rule: UserRule) => {
    const condition = (rule.trigger_condition || {}) as Record<string, unknown>;
    const triggerModule = String(rule.trigger_module || "sleep") as TriggerModule;
    const safeTriggerModule = TRIGGER_METRICS[triggerModule] ? triggerModule : "sleep";
    const actionModule = normalizeActionModule(rule.action_module);
    const actionType = String(rule.action_type || defaultActionForModule(actionModule).value);
    const metric = String(condition.metric || condition.field || TRIGGER_METRICS[safeTriggerModule][0]);
    const operator = symbolToOperator(String(condition.operator || "=="));
    const value = Number(condition.value || 0);

    const actionParams = {
      ...buildDefaultActionParams(actionModule, actionType),
      ...((rule.action_params || {}) as Record<string, string | number>),
    };

    setBuilder({
      name: rule.name,
      triggerModule: safeTriggerModule,
      metric,
      operator,
      value: Number.isFinite(value) ? value : 0,
      actionModule,
      actionType,
      actionParams,
      isActive: rule.is_active,
    });
    setEditingRuleId(rule.id);
    setNameTouched(true);
    setModalStep(1);
    setModalOpen(true);
  };

  const onTriggerModuleChange = (nextModule: TriggerModule) => {
    const metrics = TRIGGER_METRICS[nextModule];
    setBuilder((previous) => ({ ...previous, triggerModule: nextModule, metric: metrics[0] }));
  };

  const onActionModuleChange = (nextModule: ActionModule) => {
    const defaultAction = defaultActionForModule(nextModule);
    setBuilder((previous) => ({
      ...previous,
      actionModule: nextModule,
      actionType: defaultAction.value,
      actionParams: buildDefaultActionParams(nextModule, defaultAction.value),
    }));
  };

  const onActionTypeChange = (nextActionType: string) => {
    setBuilder((previous) => ({
      ...previous,
      actionType: nextActionType,
      actionParams: buildDefaultActionParams(previous.actionModule, nextActionType),
    }));
  };

  const onSaveRule = async () => {
    setSaving(true);
    setError("");
    setStatusText("");

    try {
      const normalizedParams: Record<string, string | number> = {};
      const actionDefinition = findActionDefinition(builder.actionModule, builder.actionType);
      for (const param of actionDefinition.params) {
        const raw = builder.actionParams[param.key];
        if (param.type === "number") {
          const numeric = Number(raw);
          normalizedParams[param.key] = Number.isFinite(numeric) ? numeric : Number(param.defaultValue) || 0;
        } else {
          normalizedParams[param.key] = String(raw ?? "");
        }
      }

      const payload = {
        name: builder.name.trim() || autoName,
        trigger_module: builder.triggerModule,
        trigger_condition: {
          metric: builder.metric,
          field: builder.metric,
          operator: operatorToSymbol(builder.operator),
          value: Number(builder.value),
        },
        action_module: builder.actionModule,
        action_type: builder.actionType,
        action_params: normalizedParams,
        is_active: builder.isActive,
      };

      if (editingRuleId) {
        await api.rules.updateRule(editingRuleId, payload);
        setStatusText("Rule updated.");
      } else {
        await api.rules.createRule(payload);
        setStatusText("Rule created.");
      }

      setModalOpen(false);
      resetBuilder();
      await load();
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : "Failed to save rule.");
    } finally {
      setSaving(false);
    }
  };

  const onToggleRule = async (rule: UserRule, nextValue: boolean) => {
    try {
      const updated = await api.rules.updateRule(rule.id, { is_active: nextValue });
      setRules((previous) => previous.map((item) => (item.id === rule.id ? updated : item)));
    } catch (toggleError) {
      setError(toggleError instanceof Error ? toggleError.message : "Failed to toggle rule.");
    }
  };

  const onDeleteRule = async (ruleId: string) => {
    try {
      await api.rules.deleteRule(ruleId);
      setRules((previous) => previous.filter((item) => item.id !== ruleId));
      setStatusText("Rule deleted.");
    } catch (deleteError) {
      setError(deleteError instanceof Error ? deleteError.message : "Failed to delete rule.");
    }
  };

  const onRunNow = async () => {
    setRunningNow(true);
    setError("");
    setStatusText("");
    try {
      const result = await api.rules.evaluateNow();
      setExecutionLogs((result.logs || []).slice(0, 10));
      setStatusText(`Evaluated ${result.evaluated}, matched ${result.matched}, executed ${result.executed}.`);
      await load();
    } catch (runError) {
      setError(runError instanceof Error ? runError.message : "Rule evaluation failed.");
    } finally {
      setRunningNow(false);
    }
  };

  const metricOptions = useMemo(() => {
    const defaults = TRIGGER_METRICS[builder.triggerModule];
    if (defaults.includes(builder.metric)) {
      return defaults;
    }
    return [builder.metric, ...defaults];
  }, [builder.metric, builder.triggerModule]);

  const actionDefinitions = ACTION_OPTIONS[builder.actionModule];
  const currentActionDefinition = findActionDefinition(builder.actionModule, builder.actionType);

  return (
    <div className="space-y-6">
      <AppCard className="border-accent/30 bg-gradient-to-r from-accent/10 via-accent/5 to-transparent" padding="sm">
        <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
          <div className="flex items-start gap-3">
            <div className="rounded-xl bg-accent/15 p-2 text-accent">
              <Sparkles className="h-4 w-4" />
            </div>
            <div>
              <p className="text-sm font-semibold text-text-primary">
                William suggests: You slept 4.2h last night. Add a recovery rule?
              </p>
              <p className="meta-copy mt-1">Auto-adjust your day when sleep drops below target.</p>
            </div>
          </div>
          <button
            type="button"
            onClick={() => openFromTemplate(suggestedTemplate)}
            className="rounded-xl border border-border bg-surface-raised px-3 py-2 text-sm font-medium text-text-primary"
          >
            Add Suggested Rule
          </button>
        </div>
      </AppCard>

      <header className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
        <div>
          <h1 className="text-2xl font-bold text-text-primary">Automation Rules</h1>
          <p className="meta-copy mt-1">Create intelligent IF/THEN automation for sleep, habits, study, and recovery.</p>
        </div>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={openNewRule}
            className="inline-flex items-center gap-2 rounded-xl border border-border bg-surface-raised px-4 py-2 text-sm font-medium text-text-primary"
          >
            <Plus className="h-4 w-4" /> New Rule
          </button>
          <button
            type="button"
            onClick={() => void onRunNow()}
            disabled={runningNow}
            className="inline-flex items-center gap-2 rounded-xl bg-accent px-4 py-2 text-sm font-semibold text-black disabled:opacity-60"
          >
            <PlayCircle className="h-4 w-4" /> Run Now
          </button>
        </div>
      </header>

      {error ? (
        <AppCard className="border-danger/40 bg-danger/10" padding="sm">
          <div className="flex items-start gap-2 text-danger">
            <TriangleAlert className="mt-0.5 h-4 w-4" />
            <p className="text-sm">{error}</p>
          </div>
        </AppCard>
      ) : null}

      <section className="space-y-3">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold text-text-primary">Active Rules ({activeCount}/{rules.length})</h2>
          {statusText ? <p className="meta-copy">{statusText}</p> : null}
        </div>

        {loading ? (
          <div className="grid gap-3">
            <SkeletonLoader variant="card" />
            <SkeletonLoader variant="card" />
            <SkeletonLoader variant="card" />
          </div>
        ) : rules.length === 0 ? (
          <AppCard padding="sm">
            <p className="body-copy">No rules yet. Add your first automation.</p>
          </AppCard>
        ) : (
          <div className="grid gap-3">
            {rules.map((rule, index) => (
              <motion.article
                key={rule.id}
                initial={shouldReduceMotion ? false : { opacity: 0, x: -16 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ duration: 0.2, delay: index * 0.04 }}
              >
                <AppCard
                  padding="sm"
                  className={clsx(
                    "border-border",
                    !rule.is_active && "opacity-70",
                  )}
                >
                  <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                    <div className="space-y-2">
                      <p className="text-base font-semibold text-text-primary">{rule.name}</p>
                      <div className="flex flex-wrap items-center gap-2 text-xs">
                        <span
                          className={clsx(
                            "inline-flex items-center rounded-full px-2 py-1 font-medium",
                            TRIGGER_BADGE_COLOR[rule.trigger_module] || "bg-surface-raised text-text-secondary",
                          )}
                        >
                          {TRIGGER_MODULE_LABELS[rule.trigger_module as TriggerModule] || humanizeKey(rule.trigger_module)}: {summarizeCondition((rule.trigger_condition || {}) as Record<string, unknown>)}
                        </span>
                        <ArrowRight className="h-3.5 w-3.5 text-text-secondary" />
                        <Badge label={summarizeAction(rule)} variant="accent" />
                      </div>
                    </div>

                    <div className="flex flex-wrap items-center gap-2">
                      <button
                        type="button"
                        onClick={() => void onToggleRule(rule, !rule.is_active)}
                        className="group inline-flex items-center gap-2 rounded-xl border border-border bg-surface-raised px-2 py-1.5"
                      >
                        <span className="text-xs text-text-secondary">{rule.is_active ? "Active" : "Paused"}</span>
                        <span
                          className={clsx(
                            "relative h-5 w-10 rounded-full transition",
                            rule.is_active ? "bg-accent" : "bg-surface-raised",
                          )}
                        >
                          <span
                            className={clsx(
                              "absolute top-0.5 h-4 w-4 rounded-full bg-white transition",
                              rule.is_active ? "left-5" : "left-0.5",
                            )}
                          />
                        </span>
                      </button>
                      <button
                        type="button"
                        onClick={() => openEditRule(rule)}
                        className="inline-flex items-center gap-1 rounded-xl border border-border px-2 py-1.5 text-xs text-text-primary"
                      >
                        <Pencil className="h-3.5 w-3.5" /> Edit
                      </button>
                      <button
                        type="button"
                        onClick={() => void onDeleteRule(rule.id)}
                        className="inline-flex items-center gap-1 rounded-xl border border-danger/50 px-2 py-1.5 text-xs text-danger"
                      >
                        <Trash2 className="h-3.5 w-3.5" /> Delete
                      </button>
                    </div>
                  </div>

                  <div className="mt-3 inline-flex items-center gap-1 text-xs text-text-secondary">
                    <Clock3 className="h-3.5 w-3.5" /> Last triggered: {relativeTriggered(rule.last_triggered)}
                  </div>
                </AppCard>
              </motion.article>
            ))}
          </div>
        )}
      </section>

      <section className="space-y-3">
        <h2 className="text-lg font-semibold text-text-primary">Execution Log</h2>
        <AppCard padding="sm">
          {executionLogs.length === 0 ? (
            <p className="body-copy">No execution logs yet. Click Run Now to evaluate your rules.</p>
          ) : (
            <div className="space-y-2">
              {executionLogs.slice(0, 10).map((entry) => (
                <div
                  key={entry.id}
                  className="grid gap-2 rounded-lg border border-border bg-surface-raised p-3 text-sm md:grid-cols-[1.8fr_0.7fr_0.9fr_1fr] md:items-center"
                >
                  <p className="font-medium text-text-primary">{ruleNameById.get(entry.rule_id) || "Rule"}</p>
                  <Badge label={entry.matched ? "Matched: Yes" : "Matched: No"} variant={entry.matched ? "success" : "warning"} />
                  <Badge label={entry.action_success ? "Action: Success" : "Action: Failed"} variant={entry.action_success ? "success" : "danger"} />
                  <p className="text-xs text-text-secondary">{relativeTriggered(entry.executed_at)}</p>
                </div>
              ))}
            </div>
          )}
        </AppCard>
      </section>

      <section className="space-y-3">
        <h2 className="text-lg font-semibold text-text-primary">Rule Templates</h2>
        <div className="grid gap-3 md:grid-cols-2">
          {templates.map((template, index) => (
            <motion.article
              key={`${template.name}-${index}`}
              initial={shouldReduceMotion ? false : { opacity: 0, y: 12 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, amount: 0.35 }}
              transition={{ duration: 0.2, delay: index * 0.03 }}
            >
              <AppCard padding="sm" className="h-full">
                <p className="text-base font-semibold text-text-primary">{template.name}</p>
                <p className="meta-copy mt-2">{template.summary}</p>
                <button
                  type="button"
                  onClick={() => openFromTemplate(template)}
                  className="mt-4 inline-flex items-center gap-2 rounded-xl border border-border bg-surface-raised px-3 py-2 text-sm font-medium text-text-primary"
                >
                  <Plus className="h-4 w-4" /> Add Rule
                </button>
              </AppCard>
            </motion.article>
          ))}
        </div>
      </section>

      <Modal
        isOpen={modalOpen}
        onClose={() => {
          setModalOpen(false);
          resetBuilder();
        }}
        title={editingRuleId ? "Edit Rule" : "Create New Rule"}
        size="lg"
      >
        <div className="space-y-5">
          <div className="flex items-center gap-2 text-xs text-text-secondary">
            <span className={clsx("rounded-full px-2 py-1", modalStep === 1 ? "bg-accent/20 text-accent" : "bg-surface-raised")}>1. Trigger</span>
            <span className={clsx("rounded-full px-2 py-1", modalStep === 2 ? "bg-accent/20 text-accent" : "bg-surface-raised")}>2. Action</span>
            <span className={clsx("rounded-full px-2 py-1", modalStep === 3 ? "bg-accent/20 text-accent" : "bg-surface-raised")}>3. Name & Save</span>
          </div>

          {modalStep === 1 ? (
            <div className="grid gap-3 md:grid-cols-2">
              <label className="space-y-1">
                <span className="text-sm text-text-secondary">Trigger module</span>
                <select
                  value={builder.triggerModule}
                  onChange={(event) => onTriggerModuleChange(event.target.value as TriggerModule)}
                  className="w-full rounded-xl border border-border bg-surface-raised px-3 py-2"
                >
                  {(Object.keys(TRIGGER_MODULE_LABELS) as TriggerModule[]).map((moduleKey) => (
                    <option key={moduleKey} value={moduleKey}>
                      {TRIGGER_MODULE_LABELS[moduleKey]}
                    </option>
                  ))}
                </select>
              </label>

              <label className="space-y-1">
                <span className="text-sm text-text-secondary">Metric</span>
                <select
                  value={builder.metric}
                  onChange={(event) => setBuilder((previous) => ({ ...previous, metric: event.target.value }))}
                  className="w-full rounded-xl border border-border bg-surface-raised px-3 py-2"
                >
                  {metricOptions.map((metric) => (
                    <option key={metric} value={metric}>
                      {humanizeKey(metric)}
                    </option>
                  ))}
                </select>
              </label>

              <label className="space-y-1">
                <span className="text-sm text-text-secondary">Operator</span>
                <select
                  value={builder.operator}
                  onChange={(event) => setBuilder((previous) => ({ ...previous, operator: event.target.value as OperatorKey }))}
                  className="w-full rounded-xl border border-border bg-surface-raised px-3 py-2"
                >
                  {OPERATOR_OPTIONS.map((operator) => (
                    <option key={operator.value} value={operator.value}>
                      {operator.label}
                    </option>
                  ))}
                </select>
              </label>

              <label className="space-y-1">
                <span className="text-sm text-text-secondary">Value</span>
                <input
                  type="number"
                  value={builder.value}
                  onChange={(event) => setBuilder((previous) => ({ ...previous, value: Number(event.target.value || 0) }))}
                  className="w-full rounded-xl border border-border bg-surface-raised px-3 py-2"
                />
              </label>
            </div>
          ) : null}

          {modalStep === 2 ? (
            <div className="space-y-3">
              <div className="grid gap-3 md:grid-cols-2">
                <label className="space-y-1">
                  <span className="text-sm text-text-secondary">Action module</span>
                  <select
                    value={builder.actionModule}
                    onChange={(event) => onActionModuleChange(event.target.value as ActionModule)}
                    className="w-full rounded-xl border border-border bg-surface-raised px-3 py-2"
                  >
                    <option value="scheduler">Scheduler</option>
                    <option value="notifications">Notifications</option>
                    <option value="habits">Habits</option>
                    <option value="study">Study</option>
                    <option value="chat">Chat</option>
                  </select>
                </label>

                <label className="space-y-1">
                  <span className="text-sm text-text-secondary">Action type</span>
                  <select
                    value={builder.actionType}
                    onChange={(event) => onActionTypeChange(event.target.value)}
                    className="w-full rounded-xl border border-border bg-surface-raised px-3 py-2"
                  >
                    {actionDefinitions.map((action) => (
                      <option key={action.value} value={action.value}>
                        {action.label}
                      </option>
                    ))}
                  </select>
                </label>
              </div>

              <div className="grid gap-3 md:grid-cols-2">
                {currentActionDefinition.params.map((param) => (
                  <label key={param.key} className="space-y-1">
                    <span className="text-sm text-text-secondary">{param.label}</span>
                    <input
                      type={param.type === "number" ? "number" : "text"}
                      value={String(builder.actionParams[param.key] ?? "")}
                      placeholder={param.placeholder}
                      onChange={(event) =>
                        setBuilder((previous) => ({
                          ...previous,
                          actionParams: {
                            ...previous.actionParams,
                            [param.key]: param.type === "number" ? Number(event.target.value || 0) : event.target.value,
                          },
                        }))
                      }
                      className="w-full rounded-xl border border-border bg-surface-raised px-3 py-2"
                    />
                  </label>
                ))}
              </div>
            </div>
          ) : null}

          {modalStep === 3 ? (
            <div className="space-y-3">
              <AppCard padding="sm" className="bg-surface-raised">
                <p className="text-sm text-text-secondary">Preview</p>
                <p className="mt-1 text-sm font-medium text-text-primary">
                  IF {TRIGGER_MODULE_LABELS[builder.triggerModule]} {operatorToSymbol(builder.operator)} {builder.value}{metricUnit(builder.metric)} THEN {findActionDefinition(builder.actionModule, builder.actionType).label}
                </p>
              </AppCard>

              <label className="space-y-1">
                <span className="text-sm text-text-secondary">Rule name</span>
                <input
                  value={builder.name}
                  onChange={(event) => {
                    setNameTouched(true);
                    setBuilder((previous) => ({ ...previous, name: event.target.value }));
                  }}
                  className="w-full rounded-xl border border-border bg-surface-raised px-3 py-2"
                />
              </label>

              <button
                type="button"
                onClick={() => setBuilder((previous) => ({ ...previous, isActive: !previous.isActive }))}
                className="inline-flex items-center gap-2 rounded-xl border border-border bg-surface-raised px-3 py-2 text-sm"
              >
                <span className={clsx("h-2.5 w-2.5 rounded-full", builder.isActive ? "bg-emerald-400" : "bg-rose-400")} />
                {builder.isActive ? "Active" : "Paused"}
              </button>
            </div>
          ) : null}

          <div className="flex items-center justify-between border-t border-border pt-3">
            <button
              type="button"
              onClick={() => setModalStep((previous) => Math.max(1, previous - 1) as 1 | 2 | 3)}
              disabled={modalStep === 1 || saving}
              className="rounded-xl border border-border px-3 py-2 text-sm text-text-secondary disabled:opacity-50"
            >
              Back
            </button>

            <div className="flex items-center gap-2">
              {modalStep < 3 ? (
                <button
                  type="button"
                  onClick={() => setModalStep((previous) => Math.min(3, previous + 1) as 1 | 2 | 3)}
                  className="rounded-xl bg-accent px-4 py-2 text-sm font-semibold text-black"
                >
                  Next
                </button>
              ) : (
                <button
                  type="button"
                  onClick={() => void onSaveRule()}
                  disabled={saving}
                  className="inline-flex items-center gap-2 rounded-xl bg-accent px-4 py-2 text-sm font-semibold text-black disabled:opacity-60"
                >
                  <Bot className="h-4 w-4" /> {saving ? "Saving..." : editingRuleId ? "Update Rule" : "Save Rule"}
                </button>
              )}
            </div>
          </div>
        </div>
      </Modal>
    </div>
  );
}
