import { AnimatePresence, motion } from "framer-motion";
import { LoaderCircle, Sparkles } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";

import { useAuth } from "../contexts/AuthContext";
import { api } from "../services/api";

const WILLIAM_LINES = [
  "Welcome. I am William, and I am going to calibrate your operating system.",
  "Set your rhythm first. Your wake time and sleep target shape every plan I generate.",
  "Choose your focus areas. I will create starter habits around these priorities.",
  "Everything is ready. Confirm and I will generate your first daily system.",
];

const FOCUS_OPTIONS = [
  { id: "work", label: "Work" },
  { id: "study", label: "Study" },
  { id: "fitness", label: "Fitness" },
  { id: "sleep", label: "Sleep" },
  { id: "mindfulness", label: "Mindfulness" },
  { id: "trading", label: "Trading" },
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
  const [displayName, setDisplayName] = useState(user?.display_name?.toString() || user?.full_name?.toString() || "");
  const [wakeTime, setWakeTime] = useState(user?.wake_time?.toString() || "06:30");
  const [sleepGoal, setSleepGoal] = useState(Number(user?.sleep_goal ?? 8));
  const [focusAreas, setFocusAreas] = useState<string[]>(
    Array.isArray(user?.focus_areas) && user.focus_areas.length > 0
      ? user.focus_areas.map((item) => String(item))
      : ["work"],
  );
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const progress = useMemo(() => ((step + 1) / 4) * 100, [step]);
  const typedLine = useTypewriter(WILLIAM_LINES[step] || WILLIAM_LINES[0]);

  useEffect(() => {
    if (user?.onboarding_completed) {
      navigate("/dashboard", { replace: true });
    }
  }, [navigate, user?.onboarding_completed]);

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
    setStep((current) => Math.min(current + 1, 3));
  };

  const handleBack = () => {
    setError("");
    setStep((current) => Math.max(current - 1, 0));
  };

  const handleComplete = async () => {
    setError("");
    setSubmitting(true);
    try {
      await api.auth.completeOnboarding({
        display_name: displayName.trim(),
        wake_time: wakeTime,
        sleep_goal: sleepGoal,
        focus_areas: focusAreas,
      });
      await refreshUser();
      navigate("/dashboard", { replace: true });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to finish onboarding");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="min-h-screen bg-[radial-gradient(circle_at_top_left,rgba(14,165,233,0.22),transparent_42%),radial-gradient(circle_at_bottom_right,rgba(250,204,21,0.15),transparent_40%),linear-gradient(120deg,#030712,#0f172a)] px-4 py-10 sm:px-8">
      <div className="mx-auto w-full max-w-4xl rounded-3xl border border-white/10 bg-slate-900/70 p-5 shadow-2xl backdrop-blur-md sm:p-8">
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

        <div className="mb-8 rounded-2xl border border-sky-300/20 bg-sky-500/10 p-4">
          <div className="flex items-start gap-3">
            <div className="grid h-8 w-8 place-items-center rounded-lg bg-sky-400/20 text-sky-200">
              <Sparkles className="h-4 w-4" />
            </div>
            <p className="min-h-11 text-sm leading-relaxed text-sky-100 sm:text-base">
              {typedLine}
              <span className="ml-0.5 animate-pulse">|</span>
            </p>
          </div>
        </div>

        <AnimatePresence mode="wait">
          <motion.div
            key={step}
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -12 }}
            transition={{ duration: 0.2 }}
            className="rounded-2xl border border-white/10 bg-slate-950/60 p-5 sm:p-6"
          >
            {step === 0 && (
              <div className="space-y-3">
                <h2 className="text-lg font-semibold text-white">How should William address you?</h2>
                <p className="text-sm text-slate-300">This is what I will use in briefings, nudges, and coaching.</p>
                <input
                  value={displayName}
                  onChange={(event) => setDisplayName(event.target.value)}
                  placeholder="Enter your preferred name"
                  className="w-full rounded-xl border border-slate-700 bg-slate-900 px-4 py-3 text-white outline-none ring-sky-300/40 transition focus:ring-2"
                />
              </div>
            )}

            {step === 1 && (
              <div className="grid gap-4 sm:grid-cols-2">
                <label className="space-y-2">
                  <span className="text-sm font-medium text-slate-100">Wake time</span>
                  <input
                    type="time"
                    value={wakeTime}
                    onChange={(event) => setWakeTime(event.target.value)}
                    className="w-full rounded-xl border border-slate-700 bg-slate-900 px-4 py-3 text-white outline-none ring-sky-300/40 transition focus:ring-2"
                  />
                </label>

                <label className="space-y-2">
                  <span className="text-sm font-medium text-slate-100">Sleep goal (hours)</span>
                  <input
                    type="number"
                    min={5}
                    max={12}
                    value={sleepGoal}
                    onChange={(event) => setSleepGoal(Number(event.target.value || 8))}
                    className="w-full rounded-xl border border-slate-700 bg-slate-900 px-4 py-3 text-white outline-none ring-sky-300/40 transition focus:ring-2"
                  />
                </label>
              </div>
            )}

            {step === 2 && (
              <div className="space-y-4">
                <h2 className="text-lg font-semibold text-white">Pick your current focus areas</h2>
                <p className="text-sm text-slate-300">I will create starter habits and prioritize your schedule around these.</p>
                <div className="flex flex-wrap gap-2">
                  {FOCUS_OPTIONS.map((option) => {
                    const active = focusAreas.includes(option.id);
                    return (
                      <button
                        key={option.id}
                        type="button"
                        onClick={() => toggleFocus(option.id)}
                        className={`rounded-full border px-4 py-2 text-sm font-medium transition ${
                          active
                            ? "border-emerald-300/60 bg-emerald-300/20 text-emerald-100"
                            : "border-slate-600 bg-slate-800/60 text-slate-200 hover:border-slate-400"
                        }`}
                      >
                        {option.label}
                      </button>
                    );
                  })}
                </div>
              </div>
            )}

            {step === 3 && (
              <div className="space-y-4">
                <h2 className="text-lg font-semibold text-white">Confirm your setup</h2>
                <div className="grid gap-3 text-sm text-slate-200 sm:grid-cols-2">
                  <div className="rounded-xl border border-slate-700 bg-slate-900/80 p-3">
                    <p className="text-xs uppercase tracking-wide text-slate-400">Display name</p>
                    <p className="mt-1 font-semibold text-white">{displayName}</p>
                  </div>
                  <div className="rounded-xl border border-slate-700 bg-slate-900/80 p-3">
                    <p className="text-xs uppercase tracking-wide text-slate-400">Wake time</p>
                    <p className="mt-1 font-semibold text-white">{wakeTime}</p>
                  </div>
                  <div className="rounded-xl border border-slate-700 bg-slate-900/80 p-3">
                    <p className="text-xs uppercase tracking-wide text-slate-400">Sleep goal</p>
                    <p className="mt-1 font-semibold text-white">{sleepGoal} hours</p>
                  </div>
                  <div className="rounded-xl border border-slate-700 bg-slate-900/80 p-3">
                    <p className="text-xs uppercase tracking-wide text-slate-400">Focus areas</p>
                    <p className="mt-1 font-semibold capitalize text-white">{focusAreas.join(", ")}</p>
                  </div>
                </div>
              </div>
            )}
          </motion.div>
        </AnimatePresence>

        {error ? <p className="mt-4 text-sm text-rose-300">{error}</p> : null}

        <div className="mt-6 flex items-center justify-between">
          <button
            type="button"
            onClick={handleBack}
            disabled={step === 0 || submitting}
            className="rounded-xl border border-slate-600 px-4 py-2 text-sm font-semibold text-slate-100 transition hover:border-slate-400 disabled:cursor-not-allowed disabled:opacity-50"
          >
            Back
          </button>

          {step < 3 ? (
            <button
              type="button"
              onClick={handleNext}
              disabled={submitting}
              className="rounded-xl bg-sky-500 px-5 py-2 text-sm font-semibold text-white transition hover:bg-sky-400 disabled:opacity-60"
            >
              Continue
            </button>
          ) : (
            <button
              type="button"
              onClick={handleComplete}
              disabled={submitting}
              className="inline-flex items-center gap-2 rounded-xl bg-emerald-500 px-5 py-2 text-sm font-semibold text-white transition hover:bg-emerald-400 disabled:opacity-60"
            >
              {submitting ? <LoaderCircle className="h-4 w-4 animate-spin" /> : null}
              {submitting ? "Finishing setup..." : "Complete onboarding"}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
