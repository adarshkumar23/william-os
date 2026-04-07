import { addDays, format } from "date-fns";
import { Command, Search, Sparkles } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";

import { api } from "../services/api";
import { Habit, Medicine } from "../types/api";
import Modal from "./Modal";

type QuickModal = null | "journal" | "checkin" | "sleep" | "medicine" | "workout" | "trade";

type CommandItem = {
  id: string;
  label: string;
  hint?: string;
  keywords: string[];
  run: () => Promise<void> | void;
};

function fuzzyMatch(query: string, text: string) {
  const q = query.trim().toLowerCase();
  if (!q) {
    return true;
  }
  const parts = q.split(/\s+/).filter(Boolean);
  const hay = text.toLowerCase();
  return parts.every((part) => hay.includes(part));
}

function localDateTimeInput(hoursOffset = 0) {
  const date = new Date();
  date.setHours(date.getHours() + hoursOffset);
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  const hour = String(date.getHours()).padStart(2, "0");
  const min = String(date.getMinutes()).padStart(2, "0");
  return `${year}-${month}-${day}T${hour}:${min}`;
}

export default function CommandPalette() {
  const navigate = useNavigate();

  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [selectedIndex, setSelectedIndex] = useState(0);
  const [quickModal, setQuickModal] = useState<QuickModal>(null);
  const [statusText, setStatusText] = useState("");

  const [goPrefix, setGoPrefix] = useState(false);

  const [habits, setHabits] = useState<Habit[]>([]);
  const [medicines, setMedicines] = useState<Medicine[]>([]);

  const [journalForm, setJournalForm] = useState({ content: "", passphrase: "", mood: "", tags: "" });
  const [checkinForm, setCheckinForm] = useState({ habitId: "" });
  const [sleepForm, setSleepForm] = useState({
    sleepDate: format(new Date(), "yyyy-MM-dd"),
    bedtime: localDateTimeInput(-8),
    wakeTime: localDateTimeInput(0),
    quality: "7",
  });
  const [medicineForm, setMedicineForm] = useState({ medicineId: "", taken: true, reason: "" });
  const [workoutForm, setWorkoutForm] = useState({
    workoutType: "Walk",
    durationMinutes: "30",
    calories: "120",
    workoutDate: format(new Date(), "yyyy-MM-dd"),
  });
  const [tradeForm, setTradeForm] = useState({
    symbol: "",
    exchange: "NSE",
    action: "buy",
    quantity: "1",
    price: "0",
    tradeDate: format(new Date(), "yyyy-MM-dd"),
  });

  useEffect(() => {
    const openQuickModal = (modal: QuickModal) => {
      setOpen(false);
      setQuickModal(modal);
      setStatusText("");
    };

    const commands: Record<string, () => void> = {
      h: () => navigate("/habits"),
      j: () => navigate("/journal"),
      s: () => navigate("/study"),
      f: () => navigate("/fitness"),
      t: () => navigate("/trading"),
      d: () => navigate("/dashboard"),
    };

    const onKeyDown = (event: KeyboardEvent) => {
      const target = event.target as HTMLElement | null;
      const isTyping = Boolean(
        target &&
          (target.tagName === "INPUT" ||
            target.tagName === "TEXTAREA" ||
            target.getAttribute("contenteditable") === "true"),
      );

      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        setOpen((previous) => !previous);
        return;
      }

      if (event.key === "Escape") {
        setOpen(false);
        setQuickModal(null);
        return;
      }

      if (open) {
        if (event.key === "ArrowDown") {
          event.preventDefault();
          setSelectedIndex((previous) => previous + 1);
          return;
        }
        if (event.key === "ArrowUp") {
          event.preventDefault();
          setSelectedIndex((previous) => Math.max(0, previous - 1));
          return;
        }
      }

      if (isTyping || open) {
        return;
      }

      const key = event.key.toLowerCase();
      if (goPrefix && commands[key]) {
        event.preventDefault();
        commands[key]();
        setGoPrefix(false);
        return;
      }

      if (key === "g") {
        setGoPrefix(true);
        window.setTimeout(() => setGoPrefix(false), 1200);
      }

      if (key === "/") {
        event.preventDefault();
        setOpen(true);
      }

      if (key === "k" && event.shiftKey) {
        event.preventDefault();
        openQuickModal("journal");
      }
    };

    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [goPrefix, navigate, open]);

  useEffect(() => {
    if (quickModal === "checkin") {
      void api.habits
        .list({ active_only: true, limit: 200, offset: 0 })
        .then((rows) => {
          setHabits(rows);
          if (!checkinForm.habitId && rows[0]) {
            setCheckinForm({ habitId: rows[0].id });
          }
        })
        .catch(() => setHabits([]));
    }

    if (quickModal === "medicine") {
      void api.medicine
        .list({ limit: 100, offset: 0 })
        .then((rows) => {
          setMedicines(rows);
          if (!medicineForm.medicineId && rows[0]) {
            setMedicineForm((previous) => ({ ...previous, medicineId: rows[0].id }));
          }
        })
        .catch(() => setMedicines([]));
    }
  }, [checkinForm.habitId, medicineForm.medicineId, quickModal]);

  const commands = useMemo<CommandItem[]>(
    () => [
      { id: "page-dashboard", label: "Go: Dashboard", hint: "G D", keywords: ["page", "dashboard"], run: () => navigate("/dashboard") },
      { id: "page-habits", label: "Go: Habits", hint: "G H", keywords: ["page", "habits"], run: () => navigate("/habits") },
      { id: "page-journal", label: "Go: Journal", hint: "G J", keywords: ["page", "journal"], run: () => navigate("/journal") },
      { id: "page-study", label: "Go: Study", hint: "G S", keywords: ["page", "study"], run: () => navigate("/study") },
      { id: "page-fitness", label: "Go: Fitness", hint: "G F", keywords: ["page", "fitness"], run: () => navigate("/fitness") },
      { id: "page-trading", label: "Go: Trading", hint: "G T", keywords: ["page", "trading"], run: () => navigate("/trading") },
      { id: "page-sleep", label: "Go: Sleep", keywords: ["page", "sleep"], run: () => navigate("/sleep") },
      { id: "page-decisions", label: "Go: Decisions", keywords: ["page", "decisions"], run: () => navigate("/decisions") },
      { id: "page-rules", label: "Go: Rules", keywords: ["page", "rules", "automation"], run: () => navigate("/rules") },
      {
        id: "action-journal",
        label: "/journal - open journal write modal",
        keywords: ["action", "journal", "modal", "write"],
        run: () => setQuickModal("journal"),
      },
      {
        id: "action-checkin",
        label: "/checkin - open habit check-in modal",
        keywords: ["action", "habit", "checkin", "modal"],
        run: () => setQuickModal("checkin"),
      },
      {
        id: "action-sleep",
        label: "/sleep - log sleep modal",
        keywords: ["action", "sleep", "log", "modal"],
        run: () => setQuickModal("sleep"),
      },
      {
        id: "action-medicine",
        label: "/medicine - log medicine modal",
        keywords: ["action", "medicine", "log", "modal"],
        run: () => setQuickModal("medicine"),
      },
      {
        id: "action-workout",
        label: "/workout - log workout modal",
        keywords: ["action", "fitness", "workout", "modal"],
        run: () => setQuickModal("workout"),
      },
      {
        id: "action-trade",
        label: "/trade - add trade modal",
        keywords: ["action", "trade", "trading", "modal"],
        run: () => setQuickModal("trade"),
      },
      {
        id: "action-schedule-tomorrow",
        label: "/schedule tomorrow - open tomorrow's schedule",
        keywords: ["action", "schedule", "tomorrow"],
        run: async () => {
          const tomorrow = format(addDays(new Date(), 1), "yyyy-MM-dd");
          await api.scheduler.generate(tomorrow).catch(() => undefined);
          navigate("/dashboard");
          setStatusText(`Tomorrow's schedule prepared for ${tomorrow}.`);
        },
      },
    ],
    [navigate],
  );

  const filteredCommands = useMemo(() => {
    const rows = commands.filter((command) =>
      fuzzyMatch(query, `${command.label} ${command.keywords.join(" ")}`),
    );
    return rows;
  }, [commands, query]);

  useEffect(() => {
    if (selectedIndex >= filteredCommands.length) {
      setSelectedIndex(0);
    }
  }, [filteredCommands.length, selectedIndex]);

  const onRunCommand = async (command: CommandItem | undefined) => {
    if (!command) {
      return;
    }
    setOpen(false);
    setQuery("");
    setSelectedIndex(0);
    await command.run();
  };

  const saveJournal = async () => {
    await api.journal.create({
      content: journalForm.content,
      passphrase: journalForm.passphrase,
      mood: journalForm.mood || undefined,
      tags: journalForm.tags
        .split(",")
        .map((item) => item.trim())
        .filter(Boolean),
    });
    setQuickModal(null);
    setStatusText("Journal entry saved.");
  };

  const saveCheckin = async () => {
    if (!checkinForm.habitId) {
      return;
    }
    await api.habits.checkIn(checkinForm.habitId, {
      check_date: format(new Date(), "yyyy-MM-dd"),
      completed: true,
      skipped: false,
    });
    setQuickModal(null);
    setStatusText("Habit check-in completed.");
  };

  const saveSleep = async () => {
    await api.sleep.log({
      sleep_date: sleepForm.sleepDate,
      bedtime: new Date(sleepForm.bedtime).toISOString(),
      wake_time: new Date(sleepForm.wakeTime).toISOString(),
      sleep_quality: Number(sleepForm.quality),
      interruptions: 0,
      source: "manual",
    });
    setQuickModal(null);
    setStatusText("Sleep log saved.");
  };

  const saveMedicine = async () => {
    if (!medicineForm.medicineId) {
      return;
    }
    await api.medicine.log(medicineForm.medicineId, {
      taken: medicineForm.taken,
      skipped: !medicineForm.taken,
      skip_reason: medicineForm.taken ? null : medicineForm.reason,
    });
    setQuickModal(null);
    setStatusText("Medicine log saved.");
  };

  const saveWorkout = async () => {
    await api.fitness.logWorkout({
      workout_type: workoutForm.workoutType,
      duration_minutes: Number(workoutForm.durationMinutes),
      calories_burned: Number(workoutForm.calories),
      workout_date: workoutForm.workoutDate,
    });
    setQuickModal(null);
    setStatusText("Workout logged.");
  };

  const saveTrade = async () => {
    await api.trading.logTrade({
      symbol: tradeForm.symbol.toUpperCase(),
      exchange: tradeForm.exchange,
      action: tradeForm.action,
      quantity: Number(tradeForm.quantity),
      price: Number(tradeForm.price),
      fees: 0,
      trade_date: tradeForm.tradeDate,
    });
    setQuickModal(null);
    setStatusText("Trade logged.");
  };

  return (
    <>
      {statusText ? (
        <div className="fixed bottom-4 right-4 z-40 rounded-xl border border-[rgb(var(--border))] bg-[rgb(var(--bg-elevated))] px-3 py-2 text-xs text-[rgb(var(--text-dim))] shadow-xl">
          <Sparkles className="mr-1 inline h-3.5 w-3.5 text-[rgb(var(--primary))]" />
          {statusText}
        </div>
      ) : null}

      <Modal open={open} title="Command Palette" onClose={() => setOpen(false)}>
        <div className="space-y-3">
          <div className="flex items-center gap-2 rounded-xl border border-[rgb(var(--border))] bg-[rgb(var(--bg-muted))] px-3 py-2">
            <Search className="h-4 w-4 text-[rgb(var(--text-dim))]" />
            <input
              autoFocus
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter") {
                  event.preventDefault();
                  void onRunCommand(filteredCommands[selectedIndex]);
                }
              }}
              placeholder="Search pages, actions, modules..."
              className="w-full bg-transparent text-sm outline-none"
            />
            <span className="rounded-md border border-[rgb(var(--border))] px-1.5 py-0.5 text-[10px] text-[rgb(var(--text-dim))]">
              <Command className="inline h-3 w-3" />K
            </span>
          </div>

          <div className="max-h-[46vh] space-y-1 overflow-auto">
            {filteredCommands.map((command, index) => (
              <button
                key={command.id}
                type="button"
                onClick={() => void onRunCommand(command)}
                className={`w-full rounded-lg px-3 py-2 text-left text-sm ${
                  index === selectedIndex
                    ? "bg-[rgb(var(--primary))]/20 text-[rgb(var(--primary))]"
                    : "hover:bg-[rgb(var(--bg-muted))]"
                }`}
              >
                <div className="flex items-center justify-between gap-2">
                  <span>{command.label}</span>
                  {command.hint ? <span className="text-[10px] text-[rgb(var(--text-dim))]">{command.hint}</span> : null}
                </div>
              </button>
            ))}
            {filteredCommands.length === 0 ? (
              <p className="rounded-lg bg-[rgb(var(--bg-muted))] px-3 py-2 text-sm text-[rgb(var(--text-dim))]">
                No command matched.
              </p>
            ) : null}
          </div>
        </div>
      </Modal>

      <Modal
        open={quickModal === "journal"}
        title="Quick Journal"
        onClose={() => setQuickModal(null)}
        footer={
          <button type="button" onClick={() => void saveJournal()} className="rounded-lg bg-[rgb(var(--primary))] px-3 py-2 text-sm font-semibold text-white">
            Save Journal
          </button>
        }
      >
        <div className="space-y-3">
          <textarea
            rows={5}
            value={journalForm.content}
            onChange={(event) => setJournalForm((previous) => ({ ...previous, content: event.target.value }))}
            placeholder="What happened today?"
            className="w-full rounded-xl border border-[rgb(var(--border))] bg-[rgb(var(--bg-muted))] p-3"
          />
          <div className="grid gap-3 md:grid-cols-3">
            <input
              value={journalForm.mood}
              onChange={(event) => setJournalForm((previous) => ({ ...previous, mood: event.target.value }))}
              placeholder="Mood"
              className="rounded-xl border border-[rgb(var(--border))] bg-[rgb(var(--bg-muted))] px-3 py-2"
            />
            <input
              value={journalForm.tags}
              onChange={(event) => setJournalForm((previous) => ({ ...previous, tags: event.target.value }))}
              placeholder="tags, comma,separated"
              className="rounded-xl border border-[rgb(var(--border))] bg-[rgb(var(--bg-muted))] px-3 py-2"
            />
            <input
              type="password"
              value={journalForm.passphrase}
              onChange={(event) => setJournalForm((previous) => ({ ...previous, passphrase: event.target.value }))}
              placeholder="Passphrase"
              className="rounded-xl border border-[rgb(var(--border))] bg-[rgb(var(--bg-muted))] px-3 py-2"
            />
          </div>
        </div>
      </Modal>

      <Modal
        open={quickModal === "checkin"}
        title="Quick Habit Check-in"
        onClose={() => setQuickModal(null)}
        footer={
          <button type="button" onClick={() => void saveCheckin()} className="rounded-lg bg-[rgb(var(--primary))] px-3 py-2 text-sm font-semibold text-white">
            Check In
          </button>
        }
      >
        <select
          value={checkinForm.habitId}
          onChange={(event) => setCheckinForm({ habitId: event.target.value })}
          className="w-full rounded-xl border border-[rgb(var(--border))] bg-[rgb(var(--bg-muted))] px-3 py-2"
        >
          {habits.map((habit) => (
            <option key={habit.id} value={habit.id}>
              {habit.name}
            </option>
          ))}
        </select>
      </Modal>

      <Modal
        open={quickModal === "sleep"}
        title="Quick Sleep Log"
        onClose={() => setQuickModal(null)}
        footer={
          <button type="button" onClick={() => void saveSleep()} className="rounded-lg bg-[rgb(var(--primary))] px-3 py-2 text-sm font-semibold text-white">
            Save Sleep Log
          </button>
        }
      >
        <div className="grid gap-3 md:grid-cols-2">
          <input
            type="date"
            value={sleepForm.sleepDate}
            onChange={(event) => setSleepForm((previous) => ({ ...previous, sleepDate: event.target.value }))}
            className="rounded-xl border border-[rgb(var(--border))] bg-[rgb(var(--bg-muted))] px-3 py-2"
          />
          <input
            type="number"
            min={1}
            max={10}
            step={0.1}
            value={sleepForm.quality}
            onChange={(event) => setSleepForm((previous) => ({ ...previous, quality: event.target.value }))}
            className="rounded-xl border border-[rgb(var(--border))] bg-[rgb(var(--bg-muted))] px-3 py-2"
          />
          <input
            type="datetime-local"
            value={sleepForm.bedtime}
            onChange={(event) => setSleepForm((previous) => ({ ...previous, bedtime: event.target.value }))}
            className="rounded-xl border border-[rgb(var(--border))] bg-[rgb(var(--bg-muted))] px-3 py-2"
          />
          <input
            type="datetime-local"
            value={sleepForm.wakeTime}
            onChange={(event) => setSleepForm((previous) => ({ ...previous, wakeTime: event.target.value }))}
            className="rounded-xl border border-[rgb(var(--border))] bg-[rgb(var(--bg-muted))] px-3 py-2"
          />
        </div>
      </Modal>

      <Modal
        open={quickModal === "medicine"}
        title="Quick Medicine Log"
        onClose={() => setQuickModal(null)}
        footer={
          <button type="button" onClick={() => void saveMedicine()} className="rounded-lg bg-[rgb(var(--primary))] px-3 py-2 text-sm font-semibold text-white">
            Save Medicine Log
          </button>
        }
      >
        <div className="space-y-3">
          <select
            value={medicineForm.medicineId}
            onChange={(event) => setMedicineForm((previous) => ({ ...previous, medicineId: event.target.value }))}
            className="w-full rounded-xl border border-[rgb(var(--border))] bg-[rgb(var(--bg-muted))] px-3 py-2"
          >
            {medicines.map((medicine) => (
              <option key={medicine.id} value={medicine.id}>
                {medicine.name} ({medicine.dosage})
              </option>
            ))}
          </select>
          <label className="inline-flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={medicineForm.taken}
              onChange={(event) =>
                setMedicineForm((previous) => ({ ...previous, taken: event.target.checked }))
              }
            />
            Mark as taken
          </label>
          {!medicineForm.taken ? (
            <input
              value={medicineForm.reason}
              onChange={(event) => setMedicineForm((previous) => ({ ...previous, reason: event.target.value }))}
              placeholder="Skip reason"
              className="w-full rounded-xl border border-[rgb(var(--border))] bg-[rgb(var(--bg-muted))] px-3 py-2"
            />
          ) : null}
        </div>
      </Modal>

      <Modal
        open={quickModal === "workout"}
        title="Quick Workout Log"
        onClose={() => setQuickModal(null)}
        footer={
          <button type="button" onClick={() => void saveWorkout()} className="rounded-lg bg-[rgb(var(--primary))] px-3 py-2 text-sm font-semibold text-white">
            Save Workout
          </button>
        }
      >
        <div className="grid gap-3 md:grid-cols-2">
          <input
            value={workoutForm.workoutType}
            onChange={(event) => setWorkoutForm((previous) => ({ ...previous, workoutType: event.target.value }))}
            placeholder="Workout type"
            className="rounded-xl border border-[rgb(var(--border))] bg-[rgb(var(--bg-muted))] px-3 py-2"
          />
          <input
            type="number"
            min={1}
            value={workoutForm.durationMinutes}
            onChange={(event) => setWorkoutForm((previous) => ({ ...previous, durationMinutes: event.target.value }))}
            placeholder="Duration"
            className="rounded-xl border border-[rgb(var(--border))] bg-[rgb(var(--bg-muted))] px-3 py-2"
          />
          <input
            type="number"
            min={0}
            value={workoutForm.calories}
            onChange={(event) => setWorkoutForm((previous) => ({ ...previous, calories: event.target.value }))}
            placeholder="Calories"
            className="rounded-xl border border-[rgb(var(--border))] bg-[rgb(var(--bg-muted))] px-3 py-2"
          />
          <input
            type="date"
            value={workoutForm.workoutDate}
            onChange={(event) => setWorkoutForm((previous) => ({ ...previous, workoutDate: event.target.value }))}
            className="rounded-xl border border-[rgb(var(--border))] bg-[rgb(var(--bg-muted))] px-3 py-2"
          />
        </div>
      </Modal>

      <Modal
        open={quickModal === "trade"}
        title="Quick Trade Log"
        onClose={() => setQuickModal(null)}
        footer={
          <button type="button" onClick={() => void saveTrade()} className="rounded-lg bg-[rgb(var(--primary))] px-3 py-2 text-sm font-semibold text-white">
            Save Trade
          </button>
        }
      >
        <div className="grid gap-3 md:grid-cols-2">
          <input
            value={tradeForm.symbol}
            onChange={(event) => setTradeForm((previous) => ({ ...previous, symbol: event.target.value }))}
            placeholder="Symbol"
            className="rounded-xl border border-[rgb(var(--border))] bg-[rgb(var(--bg-muted))] px-3 py-2"
          />
          <input
            value={tradeForm.exchange}
            onChange={(event) => setTradeForm((previous) => ({ ...previous, exchange: event.target.value }))}
            placeholder="Exchange"
            className="rounded-xl border border-[rgb(var(--border))] bg-[rgb(var(--bg-muted))] px-3 py-2"
          />
          <select
            value={tradeForm.action}
            onChange={(event) => setTradeForm((previous) => ({ ...previous, action: event.target.value }))}
            className="rounded-xl border border-[rgb(var(--border))] bg-[rgb(var(--bg-muted))] px-3 py-2"
          >
            <option value="buy">Buy</option>
            <option value="sell">Sell</option>
          </select>
          <input
            type="number"
            min={0.0001}
            step={0.0001}
            value={tradeForm.quantity}
            onChange={(event) => setTradeForm((previous) => ({ ...previous, quantity: event.target.value }))}
            placeholder="Quantity"
            className="rounded-xl border border-[rgb(var(--border))] bg-[rgb(var(--bg-muted))] px-3 py-2"
          />
          <input
            type="number"
            min={0.0001}
            step={0.0001}
            value={tradeForm.price}
            onChange={(event) => setTradeForm((previous) => ({ ...previous, price: event.target.value }))}
            placeholder="Price"
            className="rounded-xl border border-[rgb(var(--border))] bg-[rgb(var(--bg-muted))] px-3 py-2"
          />
          <input
            type="date"
            value={tradeForm.tradeDate}
            onChange={(event) => setTradeForm((previous) => ({ ...previous, tradeDate: event.target.value }))}
            className="rounded-xl border border-[rgb(var(--border))] bg-[rgb(var(--bg-muted))] px-3 py-2"
          />
        </div>
      </Modal>
    </>
  );
}
