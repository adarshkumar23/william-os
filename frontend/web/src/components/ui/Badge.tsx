import clsx from "clsx";

type BadgeProps = {
  label: string;
  variant?: "default" | "success" | "warning" | "danger" | "accent";
};

const variantClass: Record<NonNullable<BadgeProps["variant"]>, string> = {
  default: "bg-surface-raised text-text-secondary",
  success: "bg-success/15 text-success",
  warning: "bg-warning/15 text-warning",
  danger: "bg-danger/15 text-danger",
  accent: "bg-accent/15 text-accent",
};

export default function Badge({ label, variant = "default" }: BadgeProps) {
  return (
    <span
      className={clsx(
        "inline-flex items-center rounded-full px-2 py-1 text-xs font-medium",
        variantClass[variant],
      )}
    >
      {label}
    </span>
  );
}
