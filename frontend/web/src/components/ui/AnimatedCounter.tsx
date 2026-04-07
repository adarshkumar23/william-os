import { useEffect, useMemo, useState } from "react";
import { useReducedMotion } from "framer-motion";

type AnimatedCounterProps = {
  value: number;
  duration?: number;
  prefix?: string;
  suffix?: string;
};

function formatValue(value: number) {
  if (Number.isInteger(value)) {
    return value.toLocaleString();
  }
  return value.toLocaleString(undefined, { maximumFractionDigits: 2 });
}

export default function AnimatedCounter({
  value,
  duration = 900,
  prefix = "",
  suffix = "",
}: AnimatedCounterProps) {
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
      const elapsed = time - start;
      const progress = Math.min(elapsed / duration, 1);
      const eased = 1 - Math.pow(1 - progress, 3);
      setDisplayValue(value * eased);

      if (progress < 1) {
        frame = window.requestAnimationFrame(tick);
      }
    };

    frame = window.requestAnimationFrame(tick);
    return () => window.cancelAnimationFrame(frame);
  }, [duration, shouldReduceMotion, value]);

  const text = useMemo(() => `${prefix}${formatValue(displayValue)}${suffix}`, [displayValue, prefix, suffix]);

  return <span>{text}</span>;
}
