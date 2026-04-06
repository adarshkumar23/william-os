import { LucideIcon } from "lucide-react";
import clsx from "clsx";

type StatCardProps = {
  icon: LucideIcon;
  label: string;
  value: string;
  trend?: string;
  tone?: "primary" | "success" | "warning" | "danger";
};

const toneClass: Record<NonNullable<StatCardProps["tone"]>, string> = {
  primary: "text-[rgb(var(--primary))]",
  success: "text-[rgb(var(--success))]",
  warning: "text-[rgb(var(--warning))]",
  danger: "text-[rgb(var(--danger))]",
};

export default function StatCard({ icon: Icon, label, value, trend, tone = "primary" }: StatCardProps) {
  return (
    <article className="card p-4">
      <div className="flex items-center justify-between">
        <p className="text-xs uppercase tracking-wider text-[rgb(var(--text-dim))]">{label}</p>
        <Icon className={clsx("h-4 w-4", toneClass[tone])} />
      </div>
      <p className="mt-2 data-font text-2xl font-bold">{value}</p>
      {trend ? <p className="mt-1 text-xs text-[rgb(var(--text-dim))]">{trend}</p> : null}
    </article>
  );
}
