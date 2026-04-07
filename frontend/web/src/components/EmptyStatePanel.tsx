import { useEffect, useState } from "react";
import { Sparkles } from "lucide-react";

import { api } from "../services/api";

type EmptyStatePanelProps = {
  title: string;
  description: string;
  ctaLabel: string;
  onCta: () => void;
  moduleKey: string;
};

const moduleIllustrations: Record<string, string> = {
  habits: "M4 76 C 20 44, 48 24, 84 16 C 118 10, 150 20, 172 40 C 194 60, 198 84, 186 106 C 172 130, 140 148, 104 148 C 72 148, 44 134, 24 110 C 10 96, 2 88, 4 76 Z",
  journal: "M22 30 L148 30 C156 30 162 36 162 44 L162 126 C162 134 156 140 148 140 L22 140 C14 140 8 134 8 126 L8 44 C8 36 14 30 22 30 Z",
  medicine: "M30 20 H140 V56 H176 V112 H140 V148 H30 V112 H-6 V56 H30 Z",
  study: "M20 26 H96 C116 26 132 42 132 62 V148 H20 C12 148 6 142 6 134 V40 C6 32 12 26 20 26 Z",
  fitness: "M20 82 L54 48 L80 76 L118 34 L156 76 L186 56",
  trading: "M10 132 L10 26 L190 26 M20 118 L56 88 L88 98 L126 62 L162 76",
  sleep: "M56 94 C56 64 80 40 110 40 C122 40 134 44 144 52 C136 52 126 56 118 64 C102 80 102 106 118 122 C126 130 136 134 146 134 C136 142 124 146 112 146 C82 146 56 124 56 94 Z",
  decisions: "M24 46 H176 M34 46 V126 M166 46 V126 M24 126 H176",
};

function pickSuggestionFromAdjustments(moduleKey: string, data: Record<string, unknown>): string | null {
  const adjustments = data.adjustments as Record<string, Array<Record<string, unknown>>> | undefined;
  if (!adjustments) {
    return null;
  }
  const moduleRows = adjustments[moduleKey] || [];
  if (moduleRows[0]) {
    const item = moduleRows[0];
    const operation = String(item.operation || "adjust");
    const field = String(item.field || "your routine");
    return `AI Suggestion: ${operation} ${field} based on your current cross-module signals.`;
  }
  return null;
}

export default function EmptyStatePanel({
  title,
  description,
  ctaLabel,
  onCta,
  moduleKey,
}: EmptyStatePanelProps) {
  const [suggestion, setSuggestion] = useState("AI Suggestion: Keep tracking consistently to unlock more tailored guidance.");

  useEffect(() => {
    let active = true;

    const loadSuggestion = async () => {
      try {
        const adjustments = await api.intelligence.adjustments();
        const fromAdjustments = pickSuggestionFromAdjustments(moduleKey, adjustments);
        if (active && fromAdjustments) {
          setSuggestion(fromAdjustments);
          return;
        }
      } catch {
        // fall back to memory insights
      }

      try {
        const insights = await api.memory.insights();
        const first = insights[0] || null;
        const text = String(first?.insight || first?.title || "").trim();
        if (active && text) {
          setSuggestion(`AI Suggestion: ${text}`);
        }
      } catch {
        if (active) {
          setSuggestion("AI Suggestion: Add your first entry to start receiving personalized recommendations.");
        }
      }
    };

    void loadSuggestion();
    return () => {
      active = false;
    };
  }, [moduleKey]);

  const path = moduleIllustrations[moduleKey] || moduleIllustrations.habits;

  return (
    <article className="card p-6">
      <div className="grid gap-5 md:grid-cols-[180px_1fr] md:items-center">
        <div className="rounded-2xl border border-[rgb(var(--border))] bg-[rgb(var(--bg-muted))] p-3">
          <svg viewBox="0 0 196 164" className="h-36 w-full" role="img" aria-label={`${title} illustration`}>
            <defs>
              <linearGradient id="emptyGradient" x1="0%" y1="0%" x2="100%" y2="100%">
                <stop offset="0%" stopColor="rgb(var(--primary))" stopOpacity="0.9" />
                <stop offset="100%" stopColor="rgb(var(--success))" stopOpacity="0.65" />
              </linearGradient>
            </defs>
            <rect x="8" y="10" width="180" height="144" rx="18" fill="rgba(148, 163, 184, 0.08)" />
            <path d={path} fill="none" stroke="url(#emptyGradient)" strokeWidth="8" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        </div>

        <div>
          <h3 className="text-xl font-semibold">{title}</h3>
          <p className="mt-2 text-sm text-[rgb(var(--text-dim))]">{description}</p>

          <button
            type="button"
            onClick={onCta}
            className="mt-4 rounded-xl bg-[rgb(var(--primary))] px-4 py-2 text-sm font-semibold text-white"
          >
            {ctaLabel}
          </button>

          <div className="mt-4 rounded-xl bg-[rgb(var(--bg-muted))] p-3 text-sm text-[rgb(var(--text-dim))]">
            <Sparkles className="mr-2 inline h-4 w-4 text-[rgb(var(--primary))]" />
            {suggestion}
          </div>
        </div>
      </div>
    </article>
  );
}
