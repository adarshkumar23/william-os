import { LoaderCircle } from "lucide-react";
import clsx from "clsx";

type LoadingSpinnerProps = {
  fullPage?: boolean;
  label?: string;
  className?: string;
};

export default function LoadingSpinner({ fullPage = false, label = "Loading", className }: LoadingSpinnerProps) {
  const spinner = (
    <div className={clsx("flex items-center gap-2 text-sm text-[rgb(var(--text-dim))]", className)}>
      <LoaderCircle className="h-5 w-5 animate-spin text-[rgb(var(--primary))]" />
      <span>{label}</span>
    </div>
  );

  if (!fullPage) {
    return spinner;
  }

  return <div className="flex min-h-[60vh] items-center justify-center">{spinner}</div>;
}
