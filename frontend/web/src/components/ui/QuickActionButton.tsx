import type { ReactNode } from "react";

type QuickActionButtonProps = {
  icon: ReactNode;
  label: string;
  onClick: () => void;
  shortcut?: string;
};

export default function QuickActionButton({ icon, label, onClick, shortcut }: QuickActionButtonProps) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="inline-flex items-center gap-2 rounded-full border border-border bg-surface-raised px-4 py-2 text-sm text-text-secondary transition hover:border-border-strong hover:text-text-primary"
    >
      <span className="text-text-muted">{icon}</span>
      <span>{label}</span>
      {shortcut ? (
        <span className="ml-1 rounded-md border border-border px-1.5 py-0.5 text-[10px] uppercase tracking-wide text-text-muted">
          {shortcut}
        </span>
      ) : null}
    </button>
  );
}
