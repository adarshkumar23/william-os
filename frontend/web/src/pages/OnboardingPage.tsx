import { AnimatePresence, motion } from "framer-motion";
import { LoaderCircle } from "lucide-react";
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import { useAuth } from "../contexts/AuthContext";
import { api } from "../services/api";

const FOCUS_OPTIONS = [
  { id: "fitness", label: "Fitness", emoji: "🏃" },
  { id: "study", label: "Study", emoji: "📚" },
  { id: "trading", label: "Trading", emoji: "💰" },
  { id: "habits", label: "Habits", emoji: "🧠" },
  { id: "medicine", label: "Medicine", emoji: "💊" },
  { id: "sleep", label: "Sleep", emoji: "😴" },
];

function useTypewriter(text: string, speed = 18) {
  const [typedText, setTypedText] = useState("");

  useEffect(() => {
    setTypedText("");
    let idx = 0;
    const timer = window.setInterval(() => {
      idx += 1;
      setTypedText(text.slice(0, idx));
      if (idx >= text.length) {
        window.clearInterval(timer);
      }
    }, speed);

    return () => window.clearInterval(timer);
  }, [speed, text]);

  return typedText;
}

export default function OnboardingPage() {
  const navigate = useNavigate();
  const { user, refreshUser } = useAuth();

  const [step, setStep] = useState(0);
  const [direction, setDirection] = useState(1);
  const [displayName, setDisplayName] = useState(user?.display_name?.toString() || user?.full_name?.toString() || "");
  const [wakeTime, setWakeTime] = useState(user?.wake_time?.toString() || "06:30");
  const [sleepGoal, setSleepGoal] = useState(Number(user?.sleep_goal ?? 8));
  const [focusAreas, setFocusAreas] = useState<string[]>([]);
  const [goals, setGoals] = useState("");
  const [completionStarted, setCompletionStarted] = useState(false);
  const [completionDone, setCompletionDone] = useState(false);
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const progress = ((step + 1) / 4) * 100;
  const williamTyped = useTypewriter(
    step === 0
      ? "Hello. I'm William Salvator."
      : step === 1
        ? "Sleep is the foundation. Everything else is built on it."
        : step === 2
          ? "Choose your focus and I will shape your system around it."
          : "Perfect. I'm building your first schedule and habits now...",
  );

  useEffect(() => {
    if (user?.onboarding_completed) {
      navigate("/dashboard", { replace: true });
    }
  }, [navigate, user?.onboarding_completed]);

  useEffect(() => {
    if (step !== 3 || completionStarted || completionDone) {
      return;
    }

    let cancelled = false;

    const complete = async () => {
      setCompletionStarted(true);
      setSubmitting(true);
      setError("");
      try {
        await new Promise((resolve) => window.setTimeout(resolve, 2000));
        await api.auth.completeOnboarding({
          display_name: displayName.trim(),
          wake_time: wakeTime,
          sleep_goal: sleepGoal,
          focus_areas: focusAreas,
          goals: goals.trim() || "I want to build discipline and improve my health",
        });
        if (!cancelled) {
          await refreshUser();
          setCompletionDone(true);
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Failed to complete onboarding");
          setCompletionStarted(false);
        }
      } finally {
        if (!cancelled) {
          setSubmitting(false);
        }
      }
    };

    void complete();
    return () => {
      cancelled = true;
    };
  }, [
    completionDone,
    completionStarted,
    displayName,
    focusAreas,
    goals,
    refreshUser,
    sleepGoal,
    step,
    wakeTime,
  ]);

  const toggleFocus = (id: string) => {
    setFocusAreas((current) => {
      if (current.includes(id)) {
        if (current.length === 1) {
          return current;
        }
        return current.filter((area) => area !== id);
      }
      return [...current, id];
    });
  };

  const handleNext = () => {
    setError("");
    if (step === 0 && !displayName.trim()) {
      setError("Tell me what to call you.");
      return;
    }
    if (step === 1 && !wakeTime) {
      setError("Wake time is required.");
      return;
    }
    if (step === 2 && focusAreas.length === 0) {
      setError("Select at least one focus area.");
      return;
    }
    setDirection(1);
    setStep((current) => Math.min(current + 1, 3));
  };

  const handleBack = () => {
    setError("");
    setDirection(-1);
    setStep((current) => Math.max(current - 1, 0));
  };

  return (
    <div className="min-h-screen bg-[radial-gradient(circle_at_top,rgba(59,130,246,0.22),transparent_45%),radial-gradient(circle_at_bottom,rgba(16,185,129,0.16),transparent_40%),linear-gradient(120deg,#020617,#0f172a)] px-4 py-8 sm:px-8">
      <div className="mx-auto w-full max-w-4xl rounded-3xl border border-white/10 bg-slate-950/70 p-5 shadow-2xl backdrop-blur-md sm:p-8">
        <div className="mb-8 flex items-center justify-between gap-4">
          <div>
            <p className="text-xs uppercase tracking-[0.35em] text-sky-200/70">WILLIAM SYSTEM BOOT</p>
            <h1 className="mt-2 text-2xl font-semibold text-white sm:text-3xl">First-run onboarding</h1>
          </div>
          <div className="rounded-full border border-sky-200/30 bg-sky-400/10 px-4 py-2 text-xs font-semibold uppercase tracking-wider text-sky-100">
            Step {step + 1} / 4
          </div>
        </div>

        <div className="mb-7 h-2 overflow-hidden rounded-full bg-slate-800">
          <motion.div
            className="h-full rounded-full bg-gradient-to-r from-sky-400 via-emerald-300 to-amber-300"
            initial={{ width: 0 }}
            animate={{ width: `${progress}%` }}
            transition={{ duration: 0.25 }}
          />
        </div>

        <div className="mb-8 rounded-2xl border border-sky-300/20 bg-sky-500/10 p-4 text-sm leading-relaxed text-sky-100 sm:text-base">
          {williamTyped}
          <span className="ml-0.5 animate-pulse">|</span>
        </div>

        <AnimatePresence mode="wait">
          <motion.div
            key={step}
            initial={{ opacity: 0, x: direction > 0 ? 40 : -40 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, x: direction > 0 ? -30 : 30 }}
            transition={{ duration: 0.2 }}
            className="rounded-2xl border border-white/10 bg-slate-950/60 p-5 sm:p-6"
          >
            {step === 0 && (
              <div className="space-y-3">
                <motion.div
                  className="grid h-24 w-24 place-items-center rounded-2xl bg-gradient-to-br from-sky-400/25 to-emerald-300/25 text-5xl font-black text-white"
                  animate={{ scale: [1, 1.04, 1] }}
                  transition={{ repeat: Infinity, duration: 2.2 }}
                >
                  W
                </motion.div>
                <h2 className="text-2xl font-semibold text-white">Hello. I'm William Salvator.</h2>
                <p className="text-sm text-slate-300">
                  Your personal AI - trainer, caretaker, and therapist.
                </p>
                <label className="block space-y-2">
                  <span className="text-sm font-medium text-slate-100">What should I call you?</span>
                <input
                  value={displayName}
                  onChange={(event) => setDisplayName(event.target.value)}
                  placeholder="Asterion"
                  className="w-full rounded-xl border border-slate-700 bg-slate-900 px-4 py-3 text-white outline-none ring-sky-300/40 transition focus:ring-2"
                />
                </label>
              </div>
            )}

            {step === 1 && (
              <div className="space-y-5">
                <label className="space-y-2">
                  <span className="text-sm font-medium text-slate-100">When do you wake up?</span>
                  <input
                    type="time"
                    value={wakeTime}
                    onChange={(event) => setWakeTime(event.target.value)}
                    className="w-full rounded-xl border border-slate-700 bg-slate-900 px-4 py-3 text-white outline-none ring-sky-300/40 transition focus:ring-2"
                  />
                </label>

                <label className="space-y-2">
                  <span className="text-sm font-medium text-slate-100">
                    How many hours of sleep do you want?
                  </span>
                  <input
                    type="range"
                    min={5}
                    max={10}
                    step={0.5}
                    value={sleepGoal}
                    onChange={(event) => setSleepGoal(Number(event.target.value))}
                    className="w-full accent-sky-400"
                  />
                  <p className="text-sm text-sky-100">Target: {sleepGoal.toFixed(1)} hours</p>
                </label>

                <blockquote className="rounded-xl border border-emerald-300/25 bg-emerald-500/10 px-4 py-3 text-sm italic text-emerald-100">
                  "Sleep is the foundation. Everything else is built on it."
                </blockquote>
              </div>
            )}

            {step === 2 && (
              <div className="space-y-4">
                <h2 className="text-lg font-semibold text-white">What do you want to improve?</h2>
                <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
                  {FOCUS_OPTIONS.map((option) => {
                    const active = focusAreas.includes(option.id);
                    return (
                      <button
                        key={option.id}
                        type="button"
                        onClick={() => toggleFocus(option.id)}
                        className={`rounded-xl border px-4 py-3 text-left text-sm font-medium transition ${
                          active
                            ? "border-emerald-300/60 bg-emerald-300/20 text-emerald-100"
                            : "border-slate-600 bg-slate-800/60 text-slate-200 hover:border-slate-400"
                        }`}
                      >
                        <span className="mr-2">{option.emoji}</span>
                        {option.label}
                      </button>
                    );
                  })}
                </div>

                <label className="block space-y-2">
                  <span className="text-sm font-medium text-slate-100">What is your main goal right now?</span>
                  <textarea
                    value={goals}
                    onChange={(event) => setGoals(event.target.value)}
                    rows={3}
                    placeholder="I want to build discipline and improve my health"
                    className="w-full rounded-xl border border-slate-700 bg-slate-900 px-4 py-3 text-white outline-none ring-sky-300/40 transition focus:ring-2"
                  />
                </label>
              </div>
            )}

            {step === 3 && (
              <div className="space-y-4">
                <h2 className="text-lg font-semibold text-white">William Speaks</h2>
                <p className="text-sm text-slate-200">
                  Perfect. I'm building your first schedule and habits now...
                </p>
                {completionDone ? (
                  <p className="rounded-xl border border-emerald-300/25 bg-emerald-500/10 px-4 py-3 text-emerald-100">
                    Welcome, {displayName.trim() || "friend"}. Let's begin.
                  </p>
                ) : (
                  <div className="flex items-center gap-3 text-sky-100">
                    <LoaderCircle className="h-5 w-5 animate-spin" />
                    <span className="text-sm">Calibrating your onboarding profile...</span>
                  </div>
                )}
              </div>
            )}
          </motion.div>
        </AnimatePresence>

        {error ? <p className="mt-4 text-sm text-rose-300">{error}</p> : null}

        <div className="mt-6 flex items-center justify-between">
          <button
            type="button"
            onClick={handleBack}
            disabled={step === 0 || submitting || completionDone}
            className="rounded-xl border border-slate-600 px-4 py-2 text-sm font-semibold text-slate-100 transition hover:border-slate-400 disabled:cursor-not-allowed disabled:opacity-50"
          >
            Back
          </button>

          {step < 3 && (
            <button
              type="button"
              onClick={handleNext}
              disabled={submitting}
              className="rounded-xl bg-sky-500 px-5 py-2 text-sm font-semibold text-white transition hover:bg-sky-400 disabled:opacity-60"
            >
              Continue
            </button>
          )}

          {step === 3 && completionDone && (
            <button
              type="button"
              onClick={() => navigate("/dashboard", { replace: true })}
              className="inline-flex items-center gap-2 rounded-xl bg-emerald-500 px-5 py-2 text-sm font-semibold text-white transition hover:bg-emerald-400 disabled:opacity-60"
            >
              Enter William OS
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
