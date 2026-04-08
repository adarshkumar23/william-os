import clsx from "clsx";
import {
  Crown,
  BookOpen,
  Brain,
  CalendarRange,
  HeartPulse,
  LayoutDashboard,
  LineChart,
  MessageSquare,
  Moon,
  Pill,
  ScrollText,
  Settings,
  Target,
  Workflow,
} from "lucide-react";
import type React from "react";
import { NavLink } from "react-router-dom";

import { useAuth } from "../../contexts/AuthContext";

type NavRow = {
  to: string;
  label: string;
  icon: React.ComponentType<{ className?: string }>;
};

const groups: Array<{ label: string; items: NavRow[] }> = [
  {
    label: "Daily",
    items: [
      { to: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
      { to: "/timeline", label: "Timeline", icon: CalendarRange },
      { to: "/chat", label: "Chat", icon: MessageSquare },
      { to: "/habits", label: "Habits", icon: Target },
      { to: "/journal", label: "Journal", icon: ScrollText },
      { to: "/medicine", label: "Medicine", icon: Pill },
    ],
  },
  {
    label: "Intelligence",
    items: [
      { to: "/study", label: "Study", icon: BookOpen },
      { to: "/fitness", label: "Fitness", icon: HeartPulse },
      { to: "/sleep", label: "Sleep", icon: Moon },
      { to: "/decisions", label: "Decisions", icon: Brain },
    ],
  },
  {
    label: "Finance",
    items: [{ to: "/trading", label: "Trading", icon: LineChart }],
  },
  {
    label: "System",
    items: [
      { to: "/rules", label: "Rules", icon: Workflow },
      { to: "/settings", label: "Settings", icon: Settings },
    ],
  },
];

export default function Sidebar() {
  const { user } = useAuth();
  const name = String(user?.full_name || user?.username || "User");
  const isOwner = String(user?.role || "") === "owner";

  const renderedGroups = groups.map((group) => {
    if (group.label !== "System" || !isOwner) {
      return group;
    }
    return {
      ...group,
      items: [...group.items, { to: "/admin", label: "Admin", icon: Crown }],
    };
  });

  return (
    <aside className="hidden w-60 shrink-0 border-r border-border bg-background px-3 py-4 lg:flex lg:flex-col">
      <div className="mb-6 flex items-center gap-2 px-2">
        <p className="text-sm font-semibold tracking-tight text-text-primary">WILLIAM</p>
        <span className="rounded-full bg-accent/15 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider text-accent">
          OS
        </span>
      </div>

      <nav className="space-y-4">
        {renderedGroups.map((group) => (
          <div key={group.label}>
            <p className="section-label px-2">{group.label}</p>
            <div className="mt-2 space-y-1">
              {group.items.map((item) => {
                const Icon = item.icon;
                return (
                  <NavLink
                    key={item.to}
                    to={item.to}
                    className={({ isActive }) =>
                      clsx(
                        "flex items-center gap-2 rounded-lg px-3 py-2 text-sm transition",
                        isActive
                          ? "bg-accent/15 text-accent"
                          : "text-text-secondary hover:bg-surface-raised hover:text-text-primary",
                      )
                    }
                  >
                    <Icon className="h-4 w-4" />
                    <span>{item.label}</span>
                  </NavLink>
                );
              })}
            </div>
          </div>
        ))}
      </nav>

      <div className="mt-auto rounded-xl border border-border bg-surface p-3">
        <NavLink to="/settings" className="mb-3 inline-flex items-center gap-2 text-sm text-text-secondary hover:text-text-primary">
          <Settings className="h-4 w-4" /> Settings
        </NavLink>
        <div className="flex items-center gap-2 rounded-lg bg-surface-raised p-2">
          <div className="grid h-8 w-8 place-items-center rounded-full bg-accent/20 text-xs font-semibold text-accent">
            {name.charAt(0).toUpperCase()}
          </div>
          <div className="min-w-0">
            <p className="truncate text-sm text-text-primary">{name}</p>
            <p className="meta-copy truncate">Personal workspace</p>
          </div>
        </div>
      </div>
    </aside>
  );
}
