import type { ReactNode } from "react";

import AppCard from "./AppCard";

type EmptyStateProps = {
  icon: ReactNode | string;
  title: string;
  description: string;
  action?: ReactNode;
};

export default function EmptyState({ icon, title, description, action }: EmptyStateProps) {
  const iconNode =
    typeof icon === "string" ? (
      <span
        className="inline-flex h-14 w-14 items-center justify-center rounded-xl border border-border bg-surface-raised text-text-muted"
        aria-hidden
        dangerouslySetInnerHTML={{ __html: icon }}
      />
    ) : (
      <span className="inline-flex h-14 w-14 items-center justify-center rounded-xl border border-border bg-surface-raised text-text-muted">
        {icon}
      </span>
    );

  return (
    <AppCard padding="lg" className="text-center">
      <div className="mx-auto flex max-w-md flex-col items-center gap-3">
        {iconNode}
        <h3 className="text-lg font-semibold text-text-primary">{title}</h3>
        <p className="body-copy">{description}</p>
        {action ? <div className="pt-2">{action}</div> : null}
      </div>
    </AppCard>
  );
}
