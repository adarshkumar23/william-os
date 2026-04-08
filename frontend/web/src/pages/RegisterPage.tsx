import { LoaderCircle, UserPlus } from "lucide-react";
import { FormEvent, useEffect, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { useAuth } from "../contexts/AuthContext";

function getStrength(password: string) {
  let score = 0;
  if (password.length >= 8) score += 1;
  if (/[A-Z]/.test(password)) score += 1;
  if (/[0-9]/.test(password)) score += 1;
  if (/[^A-Za-z0-9]/.test(password)) score += 1;

  if (score <= 1) return { label: "Weak", color: "bg-rose-500", width: "33%" };
  if (score <= 3) return { label: "Medium", color: "bg-amber-500", width: "66%" };
  return { label: "Strong", color: "bg-emerald-500", width: "100%" };
}

export default function RegisterPage() {
  const navigate = useNavigate();
  const { register, isAuthenticated, isLoading, onboardingCompleted } = useAuth();

  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (isAuthenticated && !isLoading) {
      navigate(onboardingCompleted ? "/dashboard" : "/onboarding", { replace: true });
    }
  }, [isAuthenticated, isLoading, navigate, onboardingCompleted]);

  const strength = useMemo(() => getStrength(password), [password]);

  const onSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError("");

    if (!fullName.trim() || !email.trim() || !username.trim() || !password.trim()) {
      setError("All fields are required");
      return;
    }

    setSubmitting(true);
    try {
      const profile = await register({
        email: email.trim(),
        username: username.trim(),
        password,
        full_name: fullName.trim(),
        timezone: Intl.DateTimeFormat().resolvedOptions().timeZone || "Asia/Kolkata",
      });
      navigate(profile.onboarding_completed ? "/dashboard" : "/onboarding", { replace: true });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to register");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-[radial-gradient(circle_at_top,rgba(59,130,246,0.2),transparent_45%),radial-gradient(circle_at_bottom,rgba(16,185,129,0.13),transparent_40%)] p-6">
      <div className="card w-full max-w-lg p-8">
        <p className="text-xs uppercase tracking-[0.25em] text-[rgb(var(--text-dim))]">WILLIAM OS</p>
        <h1 className="mt-2 text-3xl font-bold">Create account</h1>
        <p className="mt-1 text-sm text-[rgb(var(--text-dim))]">Start your AI operating system journey.</p>

        <form className="mt-6 space-y-4" onSubmit={onSubmit}>
          <label className="block space-y-1">
            <span className="text-sm font-medium">Full name</span>
            <input
              value={fullName}
              onChange={(event) => setFullName(event.target.value)}
              className="w-full rounded-xl border border-[rgb(var(--border))] bg-[rgb(var(--bg-muted))] px-3 py-2 outline-none ring-[rgb(var(--ring))] transition focus:ring-2"
              placeholder="Adarsh Kumar"
            />
          </label>

          <div className="grid gap-4 sm:grid-cols-2">
            <label className="block space-y-1">
              <span className="text-sm font-medium">Email</span>
              <input
                type="email"
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                className="w-full rounded-xl border border-[rgb(var(--border))] bg-[rgb(var(--bg-muted))] px-3 py-2 outline-none ring-[rgb(var(--ring))] transition focus:ring-2"
                placeholder="you@example.com"
              />
            </label>

            <label className="block space-y-1">
              <span className="text-sm font-medium">Username</span>
              <input
                value={username}
                onChange={(event) => setUsername(event.target.value)}
                className="w-full rounded-xl border border-[rgb(var(--border))] bg-[rgb(var(--bg-muted))] px-3 py-2 outline-none ring-[rgb(var(--ring))] transition focus:ring-2"
                placeholder="adarsh"
              />
            </label>
          </div>

          <label className="block space-y-2">
            <span className="text-sm font-medium">Password</span>
            <input
              type="password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              className="w-full rounded-xl border border-[rgb(var(--border))] bg-[rgb(var(--bg-muted))] px-3 py-2 outline-none ring-[rgb(var(--ring))] transition focus:ring-2"
              placeholder="Create a strong password"
            />
            <div className="h-2 overflow-hidden rounded-full bg-[rgb(var(--bg-muted))]">
              <div className={`h-full ${strength.color}`} style={{ width: strength.width }} />
            </div>
            <p className="text-xs text-[rgb(var(--text-dim))]">Strength: {strength.label}</p>
          </label>

          {error ? <p className="text-sm text-[rgb(var(--danger))]">{error}</p> : null}

          <button
            type="submit"
            disabled={submitting}
            className="inline-flex w-full items-center justify-center gap-2 rounded-xl bg-[rgb(var(--primary))] px-4 py-2.5 text-sm font-semibold text-white disabled:opacity-60"
          >
            {submitting ? <LoaderCircle className="h-4 w-4 animate-spin" /> : <UserPlus className="h-4 w-4" />}
            {submitting ? "Creating account..." : "Create account"}
          </button>
        </form>

        <p className="mt-4 text-center text-sm text-[rgb(var(--text-dim))]">
          Already have an account?{" "}
          <Link className="font-semibold text-[rgb(var(--primary))]" to="/login">
            Sign in
          </Link>
        </p>
      </div>
    </div>
  );
}
