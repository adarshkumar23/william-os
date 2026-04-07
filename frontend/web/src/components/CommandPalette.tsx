import { format } from "date-fns";
import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import {
  ArrowRight,
  Bot,
  Cog,
  Command,
  Dumbbell,
  FileText,
  HeartPulse,
  LayoutDashboard,
  Moon,
  Pill,
  Search,
  Sparkles,
  Target,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";

import { reduceMotion, scaleIn } from "../lib/animations";
import { api } from "../services/api";

type CommandGroup = "Navigation" | "Quick Actions" | "AI Actions" | "Settings";

type CommandItem = {
  id: string;
  label: string;
  category: CommandGroup;
  shortcut: string;
  icon: React.ComponentType<{ className?: string }>;
  keywords: string[];
  run: () => Promise<void> | void;
};

function fuzzyScore(query: string, text: string) {
  const q = query.trim().toLowerCase();
  if (!q) {
    return 1;
  }

  let score = 0;
  let cursor = 0;
  const source = text.toLowerCase();

  for (const ch of q) {
    const index = source.indexOf(ch, cursor);
    if (index === -1) {
      return 0;
    }
    score += index === cursor ? 3 : 1;
    cursor = index + 1;
  }

  if (source.includes(q)) {
    score += 8;
  }

  return score;
}

export default function CommandPalette() {
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [selectedIndex, setSelectedIndex] = useState(0);
  const [statusText, setStatusText] = useState("");
  const shouldReduceMotion = useReducedMotion();
  const animation = reduceMotion(shouldReduceMotion, scaleIn);

  useEffect(() => {
    const onToggle = () => {
      setOpen((prev) => !prev);
      setSelectedIndex(0);
    };

    const onClose = () => setOpen(false);

    window.addEventListener("william:command-palette-toggle", onToggle);
    window.addEventListener("william:command-palette-close", onClose);

    return () => {
      window.removeEventListener("william:command-palette-toggle", onToggle);
      window.removeEventListener("william:command-palette-close", onClose);
    };
  }, []);

  const commands = useMemo<CommandItem[]>(
    () => [
      {
        id: "go-dashboard",
        label: "Go to Dashboard",
        category: "Navigation",
        shortcut: "G D",
        icon: LayoutDashboard,
        keywords: ["dashboard", "home", "overview"],
        run: () => navigate("/dashboard"),
      },
      {
        id: "go-habits",
        label: "Go to Habits",
        category: "Navigation",
        shortcut: "G H",
        icon: Target,
        keywords: ["habits", "streak"],
        run: () => navigate("/habits"),
      },
      {
        id: "go-journal",
        label: "Go to Journal",
        category: "Navigation",
        shortcut: "G J",
        icon: FileText,
        keywords: ["journal", "entries"],
        run: () => navigate("/journal"),
      },
      {
        id: "go-study",
        label: "Go to Study",
        category: "Navigation",
        shortcut: "G S",
        icon: Sparkles,
        keywords: ["study", "revision"],
        run: () => navigate("/study"),
      },
      {
        id: "go-fitness",
        label: "Go to Fitness",
        category: "Navigation",
        shortcut: "G F",
        icon: HeartPulse,
        keywords: ["fitness", "energy"],
        run: () => navigate("/fitness"),
      },
      {
        id: "go-trading",
        label: "Go to Trading",
        category: "Navigation",
        shortcut: "G T",
        icon: ArrowRight,
        keywords: ["trading", "portfolio"],
        run: () => navigate("/trading"),
      },
      {
        id: "go-sleep",
        label: "Go to Sleep",
        category: "Navigation",
        shortcut: "G L",
        icon: Moon,
        keywords: ["sleep", "recovery"],
        run: () => navigate("/sleep"),
      },
      {
        id: "qa-medicine",
        label: "Log Medicine",
        category: "Quick Actions",
        shortcut: "/medicine",
        icon: Pill,
        keywords: ["medicine", "log", "dose"],
        run: () => navigate("/medicine"),
      },
      {
        id: "qa-checkin",
        label: "Check in Habit",
        category: "Quick Actions",
        shortcut: "/checkin",
        icon: Target,
        keywords: ["habit", "checkin", "complete"],
        run: () => navigate("/habits"),
      },
      {
        id: "qa-journal",
        label: "Write Journal",
        category: "Quick Actions",
        shortcut: "/journal",
        icon: FileText,
        keywords: ["journal", "write"],
        run: () => navigate("/journal"),
      },
      {
        id: "qa-sleep",
        label: "Log Sleep",
        category: "Quick Actions",
        shortcut: "/sleep",
        icon: Moon,
        keywords: ["sleep", "log"],
        run: () => navigate("/sleep"),
      },
      {
        id: "qa-workout",
        label: "Log Workout",
        category: "Quick Actions",
        shortcut: "/workout",
        icon: Dumbbell,
        keywords: ["workout", "fitness", "log"],
        run: () => navigate("/fitness"),
      },
      {
        id: "qa-trade",
        label: "Add Trade",
        category: "Quick Actions",
        shortcut: "/trade",
        icon: ArrowRight,
        keywords: ["trade", "add", "portfolio"],
        run: () => navigate("/trading"),
      },
      {
        id: "ai-reschedule",
        label: "Trigger AI Reschedule",
        category: "AI Actions",
        shortcut: "AI",
        icon: Bot,
        keywords: ["ai", "reschedule", "schedule"],
        run: async () => {
          await api.scheduler.reschedule(format(new Date(), "yyyy-MM-dd"), {
            reason: "Triggered from command palette",
            trigger: "manual",
          });
          setStatusText("AI reschedule completed.");
          navigate("/dashboard");
        },
      },
      {
        id: "ai-briefing",
        label: "View Morning Briefing",
        category: "AI Actions",
        shortcut: "AI",
        icon: Sparkles,
        keywords: ["morning", "briefing"],
        run: () => navigate("/dashboard"),
      },
      {
        id: "open-settings",
        label: "Open Settings",
        category: "Settings",
        shortcut: "S",
        icon: Cog,
        keywords: ["settings", "preferences"],
        run: () => navigate("/settings"),
      },
    ],
    [navigate],
  );

  const filtered = useMemo(() => {
    const rows = commands
      .map((command) => {
        const text = `${command.label} ${command.category} ${command.keywords.join(" ")}`;
        return { command, score: fuzzyScore(query, text) };
      })
      .filter((item) => item.score > 0)
      .sort((a, b) => b.score - a.score)
      .map((item) => item.command);

    return rows;
  }, [commands, query]);

  useEffect(() => {
    if (selectedIndex > filtered.length - 1) {
      setSelectedIndex(0);
    }
  }, [filtered.length, selectedIndex]);

  useEffect(() => {
    if (!open) {
      return;
    }

    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setOpen(false);
        return;
      }

      if (event.key === "ArrowDown") {
        event.preventDefault();
        setSelectedIndex((prev) => Math.min(prev + 1, Math.max(0, filtered.length - 1)));
        return;
      }

      if (event.key === "ArrowUp") {
        event.preventDefault();
        setSelectedIndex((prev) => Math.max(prev - 1, 0));
        return;
      }

      if (event.key === "Enter") {
        event.preventDefault();
        const command = filtered[selectedIndex];
        if (command) {
          setOpen(false);
          setQuery("");
          void command.run();
        }
      }
    };

    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [filtered, open, selectedIndex]);

  const grouped = useMemo(() => {
    return filtered.reduce<Record<CommandGroup, CommandItem[]>>(
      (acc, command) => {
        acc[command.category].push(command);
        return acc;
      },
      {
        Navigation: [],
        "Quick Actions": [],
        "AI Actions": [],
        Settings: [],
      },
    );
  }, [filtered]);

  return (
    <>
      {statusText ? (
        <div className="fixed bottom-4 right-4 z-40 rounded-lg border border-border bg-surface px-3 py-2 text-xs text-text-secondary shadow-lg">
          {statusText}
        </div>
      ) : null}

      <AnimatePresence>
        {open ? (
          <motion.div
            className="fixed inset-0 z-[60] flex items-start justify-center bg-black/50 px-4 pt-[12vh]"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={() => setOpen(false)}
          >
            <motion.div
              className="w-full max-w-2xl overflow-hidden rounded-xl border border-border bg-surface shadow-2xl"
              initial={animation.initial}
              animate={animation.animate}
              exit={animation.initial}
              transition={animation.transition}
              onClick={(event) => event.stopPropagation()}
            >
              <div className="flex items-center gap-2 border-b border-border px-4 py-3">
                <Search className="h-4 w-4 text-text-muted" />
                <input
                  autoFocus
                  value={query}
                  onChange={(event) => {
                    setQuery(event.target.value);
                    setSelectedIndex(0);
                  }}
                  placeholder="Search commands..."
                  className="w-full bg-transparent text-sm text-text-primary outline-none"
                />
                <span className="inline-flex items-center gap-1 rounded-md border border-border px-1.5 py-0.5 text-[10px] text-text-muted">
                  <Command className="h-3 w-3" />K
                </span>
              </div>

              <div className="max-h-[60vh] overflow-y-auto p-2">
                {(["Navigation", "Quick Actions", "AI Actions", "Settings"] as CommandGroup[]).map((group) => {
                  const rows = grouped[group];
                  if (rows.length === 0) {
                    return null;
                  }

                  return (
                    <div key={group} className="mb-3">
                      <p className="section-label px-2 pb-1">{group}</p>
                      <div className="space-y-1">
                        {rows.map((command) => {
                          const absoluteIndex = filtered.findIndex((item) => item.id === command.id);
                          const Icon = command.icon;
                          const active = absoluteIndex === selectedIndex;

                          return (
                            <button
                              key={command.id}
                              type="button"
                              onClick={() => {
                                setOpen(false);
                                setQuery("");
                                void command.run();
                              }}
                              className={`flex w-full items-center justify-between rounded-lg px-3 py-2 text-left transition ${
                                active ? "bg-accent/20 text-text-primary" : "text-text-secondary hover:bg-surface-raised"
                              }`}
                            >
                              <span className="inline-flex items-center gap-2 text-sm">
                                <Icon className="h-4 w-4" />
                                {command.label}
                              </span>
                              <span className="rounded-md border border-border px-1.5 py-0.5 text-[10px] uppercase tracking-wide text-text-muted">
                                {command.shortcut}
                              </span>
                            </button>
                          );
                        })}
                      </div>
                    </div>
                  );
                })}

                {filtered.length === 0 ? (
                  <p className="rounded-lg bg-surface-raised px-3 py-2 text-sm text-text-secondary">No commands found.</p>
                ) : null}
              </div>
            </motion.div>
          </motion.div>
        ) : null}
      </AnimatePresence>
    </>
  );
}
