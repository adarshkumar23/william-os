import type { ReactNode } from "react";
import { ArrowDownRight, ArrowUpRight } from "lucide-react";

import AnimatedCounter from "./AnimatedCounter";
import AppCard from "./AppCard";

type StatCardProps = {
  label: string;
  value: number;
  unit?: string;
  trend?: number;
  trendLabel?: string;
  icon?: ReactNode;
  accent?: "accent" | "success" | "warning" | "danger" | "info";
};

const accentClass = {
  accent: "text-accent",
  success: "text-success",
  warning: "text-warning",
  danger: "text-danger",
  info: "text-info",
};

export default function StatCard({
  label,
  value,
  unit,
  trend,
  trendLabel,
  icon,
  accent = "accent",
}: StatCardProps) {
  const hasTrend = typeof trend === "number";
  const positive = (trend ?? 0) >= 0;

  return (
    <AppCard hover>
      <div className="flex items-start justify-between gap-3">
        <p className="section-label">{label}</p>
        {icon ? <span className={accentClass[accent]}>{icon}</span> : null}
      </div>
      <p className="stat-number mt-3">
        <AnimatedCounter value={value} />
        {unit ? <span className="ml-1 text-base font-medium text-text-secondary">{unit}</span> : null}
      </p>
      {hasTrend ? (
        <p className={`mt-2 inline-flex items-center gap-1 text-xs ${positive ? "text-success" : "text-danger"}`}>
          {positive ? <ArrowUpRight className="h-3.5 w-3.5" /> : <ArrowDownRight className="h-3.5 w-3.5" />}
          {Math.abs(trend ?? 0).toFixed(1)}%
          {trendLabel ? <span className="text-text-muted">{trendLabel}</span> : null}
        </p>
      ) : null}
    </AppCard>
  );
}
