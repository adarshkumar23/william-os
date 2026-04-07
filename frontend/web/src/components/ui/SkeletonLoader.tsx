import clsx from "clsx";

type SkeletonLoaderProps = {
  variant: "card" | "text" | "circle" | "stat";
  lines?: number;
};

function SkeletonBar({ className }: { className?: string }) {
  return (
    <div
      className={clsx(
        "skeleton-shimmer rounded-md bg-surface-raised",
        className,
      )}
    />
  );
}

export default function SkeletonLoader({ variant, lines = 3 }: SkeletonLoaderProps) {
  if (variant === "circle") {
    return <SkeletonBar className="h-12 w-12 rounded-full" />;
  }

  if (variant === "text") {
    return (
      <div className="space-y-2">
        {Array.from({ length: lines }).map((_, idx) => (
          <SkeletonBar key={idx} className={clsx("h-3", idx === lines - 1 ? "w-2/3" : "w-full")} />
        ))}
      </div>
    );
  }

  if (variant === "stat") {
    return (
      <div className="rounded-xl border border-border bg-surface p-4">
        <SkeletonBar className="h-3 w-24" />
        <SkeletonBar className="mt-3 h-8 w-20" />
        <SkeletonBar className="mt-3 h-3 w-32" />
      </div>
    );
  }

  return (
    <div className="rounded-xl border border-border bg-surface p-6">
      <SkeletonBar className="h-4 w-32" />
      <SkeletonBar className="mt-4 h-3 w-full" />
      <SkeletonBar className="mt-2 h-3 w-5/6" />
      <SkeletonBar className="mt-2 h-3 w-3/4" />
    </div>
  );
}
