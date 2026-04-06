import { useEffect, useMemo, useState } from "react";
import { Outlet } from "react-router-dom";

import { api } from "../services/api";
import { NotificationItem } from "../types/api";
import NotificationsPanel from "./NotificationsPanel";
import Sidebar from "./Sidebar";
import TopBar from "./TopBar";

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
    <div className="flex min-h-screen bg-[radial-gradient(circle_at_top_right,rgba(59,130,246,0.15),transparent_40%),radial-gradient(circle_at_bottom_left,rgba(16,185,129,0.1),transparent_40%)]">
      <Sidebar />
      <div className="flex min-h-screen flex-1 flex-col">
        <TopBar notificationsCount={unreadCount} onOpenNotifications={() => setOpenNotifications(true)} />
        <main className="flex-1 p-4 lg:p-6">
          <Outlet />
        </main>
      </div>

      <NotificationsPanel
        open={openNotifications}
        onClose={() => setOpenNotifications(false)}
        notifications={notifications}
      />
    </div>
  );
}
