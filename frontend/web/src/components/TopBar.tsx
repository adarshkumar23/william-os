import { Bell, Moon, Settings, Sun } from "lucide-react";
import { Link } from "react-router-dom";

import { useAuth } from "../contexts/AuthContext";
import { useTheme } from "../contexts/ThemeContext";
import { useGreeting } from "../hooks/useGreeting";

type TopBarProps = {
  notificationsCount: number;
  onOpenNotifications: () => void;
};

export default function TopBar({ notificationsCount, onOpenNotifications }: TopBarProps) {
  const { user } = useAuth();
  const { mode, toggleMode } = useTheme();
  const greeting = useGreeting((user?.full_name as string | undefined) || user?.username?.toString());

  return (
    <header className="sticky top-0 z-30 border-b border-[rgb(var(--border))] bg-[rgb(var(--bg-elevated))]/85 px-4 py-3 backdrop-blur lg:px-6">
      <div className="flex items-center justify-between gap-4">
        <div>
          <p className="text-xs uppercase tracking-widest text-[rgb(var(--text-dim))]">Control center</p>
          <h2 className="text-lg font-semibold">{greeting}</h2>
        </div>

        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={onOpenNotifications}
            className="relative rounded-xl border border-[rgb(var(--border))] p-2 transition hover:bg-[rgb(var(--bg-muted))]"
            aria-label="Open notifications"
          >
            <Bell className="h-4 w-4" />
            {notificationsCount > 0 ? (
              <span className="absolute -right-1 -top-1 rounded-full bg-[rgb(var(--danger))] px-1.5 text-[10px] font-bold text-white">
                {notificationsCount > 9 ? "9+" : notificationsCount}
              </span>
            ) : null}
          </button>

          <button
            type="button"
            onClick={toggleMode}
            className="rounded-xl border border-[rgb(var(--border))] p-2 transition hover:bg-[rgb(var(--bg-muted))]"
            aria-label="Toggle theme"
          >
            {mode === "dark" ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
          </button>

          <Link
            to="/settings"
            className="rounded-xl border border-[rgb(var(--border))] p-2 transition hover:bg-[rgb(var(--bg-muted))]"
            aria-label="Open settings"
          >
            <Settings className="h-4 w-4" />
          </Link>

          <div className="ml-1 grid h-9 w-9 place-items-center rounded-full bg-gradient-to-br from-blue-500 to-cyan-400 text-sm font-semibold text-white">
            {(user?.username?.toString().charAt(0) || "U").toUpperCase()}
          </div>
        </div>
      </div>
    </header>
  );
}
