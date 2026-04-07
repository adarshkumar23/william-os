import { useEffect, useMemo, useState } from "react";
import { Outlet } from "react-router-dom";

import { api } from "../services/api";
import { NotificationItem } from "../types/api";
import CommandPalette from "./CommandPalette";
import Sidebar from "./layout/Sidebar";
import Topbar from "./layout/Topbar";
import NotificationsPanel from "./NotificationsPanel";

export default function Layout() {
  const [openNotifications, setOpenNotifications] = useState(false);
  const [notifications, setNotifications] = useState<NotificationItem[]>([]);

  useEffect(() => {
    let active = true;

    const loadNotifications = async () => {
      try {
        const data = await api.messaging.history({ limit: 20, offset: 0 });
        if (active) {
          setNotifications(data);
        }
      } catch {
        if (active) {
          setNotifications([]);
        }
      }
    };

    void loadNotifications();
    const interval = window.setInterval(() => void loadNotifications(), 30000);

    return () => {
      active = false;
      window.clearInterval(interval);
    };
  }, []);

  const unreadCount = useMemo(
    () => notifications.filter((notification) => !notification.delivered || notification.error).length,
    [notifications],
  );

  return (
    <div className="flex min-h-screen bg-background">
      <Sidebar />
      <div className="flex min-h-screen flex-1 flex-col">
        <Topbar notificationsCount={unreadCount} onOpenNotifications={() => setOpenNotifications(true)} />
        <main className="flex-1">
          <div className="mx-auto flex w-full max-w-6xl flex-col gap-6 px-8 py-8">
            <Outlet />
          </div>
        </main>
      </div>

      <NotificationsPanel
        open={openNotifications}
        onClose={() => setOpenNotifications(false)}
        notifications={notifications}
      />

      <CommandPalette />
    </div>
  );
}
