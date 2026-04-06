import { FormEvent, useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";

import { useAuth } from "../contexts/AuthContext";

export default function LoginPage() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const from = (location.state as { from?: string } | null)?.from || "/";

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();
    setError(null);
    setLoading(true);
    try {
      await login(email, password);
      navigate(from, { replace: true });
    } catch (err: any) {
      setError(err?.response?.data?.error || "Login failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="grid min-h-screen place-items-center px-4">
      <form className="panel w-full max-w-md space-y-4 p-6" onSubmit={handleSubmit}>
        <h1 className="font-display text-3xl font-bold">Welcome Back</h1>
        <p className="text-sm text-slate-500 dark:text-slate-400">Sign in to WILLIAM OS.</p>

        <input
          className="w-full rounded-xl border border-slate-300 bg-white/80 p-3 dark:border-slate-700 dark:bg-slate-900"
          type="email"
          placeholder="Email"
          value={email}
          onChange={(event) => setEmail(event.target.value)}
          required
        />
        <input
          className="w-full rounded-xl border border-slate-300 bg-white/80 p-3 dark:border-slate-700 dark:bg-slate-900"
          type="password"
          placeholder="Password"
          value={password}
          onChange={(event) => setPassword(event.target.value)}
          required
        />

        {error && <p className="text-sm text-red-600">{error}</p>}

        <button className="btn-primary w-full" disabled={loading} type="submit">
          {loading ? "Signing in..." : "Sign In"}
        </button>

        <p className="text-sm text-slate-600 dark:text-slate-300">
          Need an account? <Link className="text-william-electric underline" to="/register">Register</Link>
        </p>
      </form>
    </div>
  );
}
