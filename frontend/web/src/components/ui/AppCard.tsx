import clsx from "clsx";
import type { PropsWithChildren } from "react";

type AppCardProps = PropsWithChildren<{
  className?: string;
  padding?: "sm" | "md" | "lg";
  hover?: boolean;
}>;

const paddingClass: Record<NonNullable<AppCardProps["padding"]>, string> = {
  sm: "p-4",
  md: "p-6",
  lg: "p-8",
};

export default function AppCard({ children, className, padding = "md", hover = false }: AppCardProps) {
  return (
    <section
      className={clsx(
        "rounded-xl border border-border bg-surface",
        paddingClass[padding],
        hover && "transition duration-200 hover:-translate-y-0.5 hover:border-border-strong hover:shadow-lg",
        className,
      )}
    >
      {children}
    </section>
  );
}
