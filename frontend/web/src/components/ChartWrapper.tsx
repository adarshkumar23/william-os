import type { ReactNode } from "react";

type ChartWrapperProps = {
  title: string;
  subtitle?: string;
  children: ReactNode;
};

export default function ChartWrapper({ title, subtitle, children }: ChartWrapperProps) {
  return (
    <section className="card p-4">
      <header className="mb-3">
        <h3 className="text-base font-semibold">{title}</h3>
        {subtitle ? <p className="text-xs text-[rgb(var(--text-dim))]">{subtitle}</p> : null}
      </header>
      <div className="h-64 w-full">{children}</div>
    </section>
  );
}
