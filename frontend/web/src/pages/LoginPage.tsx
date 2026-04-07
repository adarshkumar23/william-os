import { LoaderCircle, LogIn } from "lucide-react";
import { FormEvent, useEffect, useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";

import { useAuth } from "../contexts/AuthContext";

export default function LoginPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const { isAuthenticated, login, isLoading } = useAuth();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [totpCode, setTotpCode] = useState("");
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (isAuthenticated) {
      navigate("/dashboard", { replace: true });
    }
  }, [isAuthenticated, navigate]);

  const onSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError("");

    if (!email.trim()) {
      setError("Email is required");
      return;
    }
    if (!password.trim()) {
      setError("Password is required");
      return;
    }

    setSubmitting(true);
    try {
      await login(email.trim(), password, totpCode.trim() || undefined);
      const from = (location.state as { from?: string } | null)?.from;
      navigate(from || "/dashboard", { replace: true });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to sign in");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-[radial-gradient(circle_at_top,rgba(59,130,246,0.22),transparent_45%),radial-gradient(circle_at_bottom,rgba(16,185,129,0.15),transparent_40%)] p-6">
      <div className="card w-full max-w-md p-8">
        <p className="text-xs uppercase tracking-[0.25em] text-[rgb(var(--text-dim))]">WILLIAM OS</p>
        <h1 className="mt-2 text-3xl font-bold">Sign in</h1>
        <p className="mt-1 text-sm text-[rgb(var(--text-dim))]">Access your mission control dashboard.</p>

        <form className="mt-6 space-y-4" onSubmit={onSubmit}>
          <label className="block space-y-1">
            <span className="text-sm font-medium">Email</span>
            <input
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              type="email"
              autoComplete="email"
              className="w-full rounded-xl border border-[rgb(var(--border))] bg-[rgb(var(--bg-muted))] px-3 py-2 outline-none ring-[rgb(var(--ring))] transition focus:ring-2"
              placeholder="you@example.com"
            />
          </label>

          <label className="block space-y-1">
            <span className="text-sm font-medium">Password</span>
            <input
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              type="password"
              autoComplete="current-password"
              className="w-full rounded-xl border border-[rgb(var(--border))] bg-[rgb(var(--bg-muted))] px-3 py-2 outline-none ring-[rgb(var(--ring))] transition focus:ring-2"
              placeholder="Your password"
            />
          </label>

          <label className="block space-y-1">
            <span className="text-sm font-medium">2FA code (if enabled)</span>
            <input
              value={totpCode}
              onChange={(event) => setTotpCode(event.target.value)}
              type="text"
              autoComplete="one-time-code"
              className="w-full rounded-xl border border-[rgb(var(--border))] bg-[rgb(var(--bg-muted))] px-3 py-2 outline-none ring-[rgb(var(--ring))] transition focus:ring-2"
              placeholder="123456"
              inputMode="numeric"
            />
          </label>

          {error ? <p className="text-sm text-[rgb(var(--danger))]">{error}</p> : null}

          <button
            type="submit"
            disabled={submitting || isLoading}
            className="inline-flex w-full items-center justify-center gap-2 rounded-xl bg-[rgb(var(--primary))] px-4 py-2.5 text-sm font-semibold text-white disabled:opacity-60"
          >
            {submitting ? <LoaderCircle className="h-4 w-4 animate-spin" /> : <LogIn className="h-4 w-4" />}
            {submitting ? "Signing in..." : "Sign In"}
          </button>
        </form>

        <p className="mt-4 text-center text-sm text-[rgb(var(--text-dim))]">
          New here?{" "}
          <Link className="font-semibold text-[rgb(var(--primary))]" to="/register">
            Create account
          </Link>
        </p>
      </div>
    </div>
  );
}
