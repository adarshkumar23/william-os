import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import { BellRing, X } from "lucide-react";

import { reduceMotion, slideInRight } from "../lib/animations";
import { NotificationItem } from "../types/api";

type NotificationsPanelProps = {
  open: boolean;
  onClose: () => void;
  notifications: NotificationItem[];
};

export default function NotificationsPanel({ open, onClose, notifications }: NotificationsPanelProps) {
  const shouldReduceMotion = useReducedMotion();
  const panelMotion = reduceMotion(shouldReduceMotion, slideInRight);

  return (
    <AnimatePresence>
      {open ? (
        <>
          <motion.div
            className="fixed inset-0 z-40 bg-black/50"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={onClose}
          />
          <motion.aside
            className="fixed right-0 top-0 z-50 h-full w-full max-w-md border-l border-border bg-surface p-4"
            initial={panelMotion.initial}
            animate={panelMotion.animate}
            exit={{ opacity: 0, x: 18 }}
            transition={panelMotion.transition}
          >
            <header className="mb-4 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <BellRing className="h-5 w-5 text-accent" />
                <h3 className="text-lg font-semibold text-text-primary">Notifications</h3>
              </div>
              <button
                type="button"
                onClick={onClose}
                className="rounded-lg border border-border p-2 text-text-secondary"
              >
                <X className="h-4 w-4" />
              </button>
            </header>

            <div className="space-y-3 overflow-y-auto pb-8">
              {notifications.length === 0 ? (
                <p className="body-copy">No notifications yet.</p>
              ) : (
                notifications.map((notification) => (
                  <article key={notification.id} className="rounded-xl border border-border bg-surface-raised p-3">
                    <p className="section-label">
                      {notification.notification_type}
                    </p>
                    <p className="mt-1 text-sm text-text-primary">
                      {typeof notification.payload?.body === "string"
                        ? notification.payload.body
                        : JSON.stringify(notification.payload || {}, null, 2)}
                    </p>
                    <p className="meta-copy mt-2">{notification.sent_at}</p>
                  </article>
                ))
              )}
            </div>
          </motion.aside>
        </>
      ) : null}
    </AnimatePresence>
  );
}
