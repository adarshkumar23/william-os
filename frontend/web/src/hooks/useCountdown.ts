import { useEffect, useMemo, useState } from "react";

export function useCountdown(target?: Date | null) {
  const [now, setNow] = useState(Date.now());

  useEffect(() => {
    if (!target) {
      return;
    }
    const timer = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(timer);
  }, [target]);

  return useMemo(() => {
    if (!target) {
      return "--:--:--";
    }
    const diff = Math.max(0, target.getTime() - now);
    const h = Math.floor(diff / 3_600_000);
    const m = Math.floor((diff % 3_600_000) / 60_000);
    const s = Math.floor((diff % 60_000) / 1_000);
    return `${h.toString().padStart(2, "0")}:${m.toString().padStart(2, "0")}:${s
      .toString()
      .padStart(2, "0")}`;
  }, [now, target]);
}
