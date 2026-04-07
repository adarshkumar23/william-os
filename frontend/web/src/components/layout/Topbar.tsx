import { Bell, Command, Moon, Sun } from "lucide-react";
import { useMemo } from "react";
import { useLocation } from "react-router-dom";

import { useAuth } from "../../contexts/AuthContext";
import { useTheme } from "../../contexts/ThemeContext";

type TopbarProps = {
  notificationsCount: number;
  onOpenNotifications: () => void;
};

const titleMap: Record<string, string> = {
  "/dashboard": "Dashboard",
  "/habits": "Habits",
  "/journal": "Journal",
  "/medicine": "Medicine",
  "/study": "Study",
  "/fitness": "Fitness",
  "/trading": "Trading",
  "/sleep": "Sleep",
  "/decisions": "Decisions",
  "/rules": "Rules Engine",
  "/settings": "Settings",
};

export default function Topbar({ notificationsCount, onOpenNotifications }: TopbarProps) {
  const location = useLocation();
  const { mode, toggleMode } = useTheme();
  const { user } = useAuth();

  const title = useMemo(() => titleMap[location.pathname] || "WILLIAM", [location.pathname]);
  const initials = String(user?.username || "U").charAt(0).toUpperCase();

  return (
    <header className="sticky top-0 z-30 h-14 border-b border-border bg-background/90 px-6 backdrop-blur">
      <div className="flex h-full items-center justify-between gap-4">
        <h1 className="text-xl font-semibold tracking-tight text-text-primary">{title}</h1>

        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => window.dispatchEvent(new Event("william:command-palette-toggle"))}
            className="inline-flex items-center gap-2 rounded-lg border border-border bg-surface px-3 py-1.5 text-xs text-text-secondary transition hover:border-border-strong hover:text-text-primary"
          >
            <Command className="h-3.5 w-3.5" />
            <span>Search</span>
            <span className="rounded-md border border-border px-1 py-0.5 text-[10px]">Cmd K</span>
          </button>

          <button
            type="button"
            onClick={onOpenNotifications}
            className="relative rounded-lg border border-border bg-surface p-2 text-text-secondary transition hover:border-border-strong hover:text-text-primary"
            aria-label="Open notifications"
          >
            <Bell className="h-4 w-4" />
            {notificationsCount > 0 ? (
              <span className="absolute -right-1 -top-1 rounded-full bg-danger px-1.5 text-[10px] font-semibold text-white">
                {notificationsCount > 9 ? "9+" : notificationsCount}
              </span>
            ) : null}
          </button>

          <button
            type="button"
            onClick={toggleMode}
            className="rounded-lg border border-border bg-surface p-2 text-text-secondary transition hover:border-border-strong hover:text-text-primary"
            aria-label="Toggle theme"
          >
            {mode === "dark" ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
          </button>

          <div className="grid h-8 w-8 place-items-center rounded-full bg-accent/20 text-sm font-semibold text-accent">{initials}</div>
        </div>
      </div>
    </header>
  );
}
