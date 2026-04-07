import type { ReactNode } from "react";

type SectionHeaderProps = {
  title: string;
  subtitle?: string;
  action?: ReactNode;
};

export default function SectionHeader({ title, subtitle, action }: SectionHeaderProps) {
  return (
    <header className="flex items-start justify-between gap-4">
      <div>
        <p className="section-label">{title}</p>
        {subtitle ? <p className="mt-2 body-copy">{subtitle}</p> : null}
      </div>
      {action ? <div>{action}</div> : null}
    </header>
  );
}
