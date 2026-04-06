import { AnimatePresence, motion } from "framer-motion";
import { BellRing, X } from "lucide-react";

import { NotificationItem } from "../types/api";

type NotificationsPanelProps = {
  open: boolean;
  onClose: () => void;
  notifications: NotificationItem[];
};

export default function NotificationsPanel({ open, onClose, notifications }: NotificationsPanelProps) {
  return (
    <AnimatePresence>
      {open ? (
        <>
          <motion.div
            className="fixed inset-0 z-40 bg-slate-950/45"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={onClose}
          />
          <motion.aside
            className="fixed right-0 top-0 z-50 h-full w-full max-w-md border-l border-[rgb(var(--border))] bg-[rgb(var(--bg-elevated))] p-4"
            initial={{ x: "100%" }}
            animate={{ x: 0 }}
            exit={{ x: "100%" }}
            transition={{ type: "spring", stiffness: 240, damping: 28 }}
          >
            <header className="mb-4 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <BellRing className="h-5 w-5 text-[rgb(var(--primary))]" />
                <h3 className="text-lg font-semibold">Notifications</h3>
              </div>
              <button
                type="button"
                onClick={onClose}
                className="rounded-lg border border-[rgb(var(--border))] p-2"
              >
                <X className="h-4 w-4" />
              </button>
            </header>

            <div className="space-y-3 overflow-y-auto pb-8">
              {notifications.length === 0 ? (
                <p className="text-sm text-[rgb(var(--text-dim))]">No notifications yet.</p>
              ) : (
                notifications.map((notification) => (
                  <article key={notification.id} className="card p-3">
                    <p className="text-xs uppercase tracking-wide text-[rgb(var(--text-dim))]">
                      {notification.notification_type}
                    </p>
                    <p className="mt-1 text-sm">
                      {typeof notification.payload?.body === "string"
                        ? notification.payload.body
                        : JSON.stringify(notification.payload || {}, null, 2)}
                    </p>
                    <p className="mt-2 data-font text-xs text-[rgb(var(--text-dim))]">{notification.sent_at}</p>
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
