import { useEffect, useMemo, useState } from "react";
import { useReducedMotion } from "framer-motion";

type ProgressRingProps = {
  value: number;
  size?: "sm" | "md" | "lg";
  color?: string;
  label?: string;
  sublabel?: string;
};

const ringSize = {
  sm: { diameter: 76, stroke: 7 },
  md: { diameter: 112, stroke: 9 },
  lg: { diameter: 150, stroke: 11 },
};

export default function ProgressRing({
  value,
  size = "md",
  color = "rgb(var(--color-accent))",
  label,
  sublabel,
}: ProgressRingProps) {
  const shouldReduceMotion = useReducedMotion();
  const [displayValue, setDisplayValue] = useState(0);

  useEffect(() => {
    if (shouldReduceMotion) {
      setDisplayValue(value);
      return;
    }

    let frame = 0;
    let start: number | null = null;

    const tick = (time: number) => {
      if (start === null) {
        start = time;
      }
      const progress = Math.min((time - start) / 700, 1);
      const eased = 1 - Math.pow(1 - progress, 3);
      setDisplayValue(value * eased);
      if (progress < 1) {
        frame = requestAnimationFrame(tick);
      }
    };

    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, [shouldReduceMotion, value]);

  const normalized = Math.max(0, Math.min(100, displayValue));
  const { diameter, stroke } = ringSize[size];
  const radius = (diameter - stroke) / 2;
  const circumference = Math.PI * 2 * radius;
  const offset = circumference - (normalized / 100) * circumference;
  const glow = normalized > 80 ? "drop-shadow(0 0 6px rgba(99,102,241,0.55))" : "none";

  const textSize = useMemo(() => {
    if (size === "sm") return "text-xl";
    if (size === "lg") return "text-4xl";
    return "text-3xl";
  }, [size]);

  return (
    <div className="inline-flex flex-col items-center gap-2">
      <div className="relative" style={{ width: diameter, height: diameter }}>
        <svg width={diameter} height={diameter} className="-rotate-90">
          <circle
            cx={diameter / 2}
            cy={diameter / 2}
            r={radius}
            stroke="rgb(var(--color-border-strong))"
            strokeWidth={stroke}
            fill="none"
          />
          <circle
            cx={diameter / 2}
            cy={diameter / 2}
            r={radius}
            stroke={color}
            strokeWidth={stroke}
            fill="none"
            strokeLinecap="round"
            strokeDasharray={circumference}
            strokeDashoffset={offset}
            style={{ transition: shouldReduceMotion ? "none" : "stroke-dashoffset 700ms ease", filter: glow }}
          />
        </svg>
        <div className="absolute inset-0 grid place-items-center">
          <p className={`${textSize} font-bold tabular-nums text-text-primary`}>{Math.round(normalized)}</p>
        </div>
      </div>
      {label ? <p className="section-label">{label}</p> : null}
      {sublabel ? <p className="meta-copy">{sublabel}</p> : null}
    </div>
  );
}
