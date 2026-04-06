import { useEffect, useState } from "react";
import { NavLink, useNavigate } from "react-router-dom";

import { useAuth } from "../contexts/AuthContext";

const navItems = [
  { to: "/", label: "Dashboard" },
  { to: "/habits", label: "Habits" },
  { to: "/journal", label: "Journal" },
  { to: "/medicine", label: "Medicine" },
  { to: "/study", label: "Study" },
  { to: "/fitness", label: "Fitness" },
  { to: "/settings", label: "Settings" },
];

export default function Navbar() {
  const { currentUser, logout } = useAuth();
  const navigate = useNavigate();

  const [dark, setDark] = useState(() => localStorage.getItem("william_theme") === "dark");

  useEffect(() => {
    document.documentElement.classList.toggle("dark", dark);
    localStorage.setItem("william_theme", dark ? "dark" : "light");
  }, [dark]);

  return (
    <header className="sticky top-0 z-40 border-b border-slate-200/60 bg-white/75 backdrop-blur-md dark:border-slate-700/50 dark:bg-slate-900/75">
      <div className="mx-auto flex max-w-7xl flex-wrap items-center gap-3 px-4 py-3 md:px-6">
        <div className="mr-4 flex items-center gap-2">
          <div className="h-9 w-9 rounded-xl bg-gradient-to-br from-william-electric to-william-ember" />
          <div>
            <p className="font-display text-sm uppercase tracking-[0.2em] text-slate-500 dark:text-slate-400">
              WILLIAM
            </p>
            <p className="font-display text-lg font-bold">OS</p>
          </div>
        </div>

        <nav className="flex flex-wrap gap-1">
          {navItems.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) =>
                [
                  "rounded-xl px-3 py-2 text-sm font-semibold transition",
                  isActive
                    ? "bg-slate-900 text-white dark:bg-slate-100 dark:text-slate-900"
                    : "text-slate-600 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-800",
                ].join(" ")
              }
            >
              {item.label}
            </NavLink>
          ))}
        </nav>

        <div className="ml-auto flex items-center gap-2">
          <button className="btn-secondary" onClick={() => setDark((v) => !v)} type="button">
            {dark ? "Light" : "Dark"}
          </button>
          <button
            className="btn-secondary"
            onClick={() => {
              logout();
              navigate("/login");
            }}
            type="button"
          >
            Logout
          </button>
          <div className="rounded-xl border border-slate-300 px-3 py-2 text-xs dark:border-slate-700">
            {currentUser?.username}
          </div>
        </div>
      </div>
    </header>
  );
}
