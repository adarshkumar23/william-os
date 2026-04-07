import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import { AlertTriangle, CheckCircle2, Info, X } from "lucide-react";
import { useState } from "react";

import { fadeInUp, reduceMotion } from "../../lib/animations";

type InsightBannerProps = {
  text: string;
  type?: "info" | "warning" | "danger" | "success";
  dismissible?: boolean;
};

const typeStyles = {
  info: {
    wrap: "border-info/40 bg-info/10 text-info",
    icon: Info,
  },
  warning: {
    wrap: "border-warning/40 bg-warning/10 text-warning",
    icon: AlertTriangle,
  },
  danger: {
    wrap: "border-danger/40 bg-danger/10 text-danger",
    icon: AlertTriangle,
  },
  success: {
    wrap: "border-success/40 bg-success/10 text-success",
    icon: CheckCircle2,
  },
};

export default function InsightBanner({ text, type = "info", dismissible = false }: InsightBannerProps) {
  const [hidden, setHidden] = useState(false);
  const shouldReduceMotion = useReducedMotion();
  const Icon = typeStyles[type].icon;
  const animation = reduceMotion(shouldReduceMotion, fadeInUp);

  return (
    <AnimatePresence>
      {!hidden ? (
        <motion.article
          initial={animation.initial}
          animate={animation.animate}
          exit={{ opacity: 0, y: -8 }}
          transition={animation.transition}
          className={`flex items-start gap-3 rounded-xl border-l-4 p-3 ${typeStyles[type].wrap}`}
        >
          <Icon className="mt-0.5 h-4 w-4 shrink-0" />
          <p className="flex-1 text-sm leading-relaxed text-text-primary">{text}</p>
          {dismissible ? (
            <button type="button" className="rounded-lg p-1 hover:bg-black/10" onClick={() => setHidden(true)}>
              <X className="h-4 w-4" />
            </button>
          ) : null}
        </motion.article>
      ) : null}
    </AnimatePresence>
  );
}
