import {
  BarChart3,
  BookOpen,
  Brain,
  HeartPulse,
  LayoutDashboard,
  LineChart,
  Moon,
  Pill,
  ScrollText,
  Settings,
  Sunrise,
  Target,
} from "lucide-react";
import clsx from "clsx";
import { NavLink } from "react-router-dom";

const links = [
  { to: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { to: "/habits", label: "Habits", icon: Target },
  { to: "/journal", label: "Journal", icon: ScrollText },
  { to: "/medicine", label: "Medicine", icon: Pill },
  { to: "/study", label: "Study", icon: BookOpen },
  { to: "/fitness", label: "Fitness", icon: HeartPulse },
  { to: "/trading", label: "Trading", icon: LineChart },
  { to: "/sleep", label: "Sleep", icon: Moon },
  { to: "/decisions", label: "Decisions", icon: Brain },
  { to: "/settings", label: "Settings", icon: Settings },
];

export default function Sidebar() {
  return (
    <aside className="hidden w-72 flex-col border-r border-[rgb(var(--border))] bg-[rgb(var(--bg-elevated))] p-4 lg:flex">
      <div className="mb-6 rounded-2xl bg-gradient-to-br from-blue-600/25 via-emerald-500/10 to-transparent p-4">
        <p className="text-xs uppercase tracking-widest text-[rgb(var(--text-dim))]">WILLIAM OS</p>
        <h1 className="mt-1 text-2xl font-bold">Mission Control</h1>
        <p className="mt-2 text-sm text-[rgb(var(--text-dim))]">Your life operating system in one dashboard.</p>
      </div>

      <nav className="space-y-1">
        {links.map(({ to, label, icon: Icon }) => (
          <NavLink
            key={to}
            to={to}
            className={({ isActive }) =>
              clsx(
                "flex items-center gap-3 rounded-xl px-3 py-2 text-sm font-medium transition",
                isActive
                  ? "bg-[rgb(var(--primary))]/20 text-[rgb(var(--primary))]"
                  : "text-[rgb(var(--text-dim))] hover:bg-[rgb(var(--bg-muted))] hover:text-[rgb(var(--text))]",
              )
            }
          >
            <Icon className="h-4 w-4" />
            {label}
          </NavLink>
        ))}
      </nav>

      <div className="mt-auto rounded-2xl border border-[rgb(var(--border))] bg-[rgb(var(--bg-muted))] p-3">
        <p className="text-xs text-[rgb(var(--text-dim))]">Daily objective</p>
        <p className="mt-1 text-sm font-medium">Stay consistent across habits, study, and sleep.</p>
        <div className="mt-2 inline-flex items-center gap-1 rounded-lg bg-blue-500/20 px-2 py-1 text-xs font-medium text-blue-400">
          <Sunrise className="h-3.5 w-3.5" /> Morning briefing ready
        </div>
      </div>
    </aside>
  );
}
