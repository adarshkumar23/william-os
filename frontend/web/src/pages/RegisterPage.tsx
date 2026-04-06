import { FormEvent, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { useAuth } from "../contexts/AuthContext";

export default function RegisterPage() {
  const { register } = useAuth();
  const navigate = useNavigate();

  const [email, setEmail] = useState("");
  const [username, setUsername] = useState("");
  const [fullName, setFullName] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();
    setError(null);
    setLoading(true);
    try {
      await register({ email, username, fullName, password });
      navigate("/", { replace: true });
    } catch (err: any) {
      setError(err?.response?.data?.error || "Register failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="grid min-h-screen place-items-center px-4">
      <form className="panel w-full max-w-lg space-y-4 p-6" onSubmit={handleSubmit}>
        <h1 className="font-display text-3xl font-bold">Create Account</h1>
        <p className="text-sm text-slate-500 dark:text-slate-400">Start your personal AI operating system.</p>

        <div className="grid gap-3 md:grid-cols-2">
          <input
            className="rounded-xl border border-slate-300 bg-white/80 p-3 dark:border-slate-700 dark:bg-slate-900"
            type="text"
            placeholder="Full name"
            value={fullName}
            onChange={(event) => setFullName(event.target.value)}
            required
          />
          <input
            className="rounded-xl border border-slate-300 bg-white/80 p-3 dark:border-slate-700 dark:bg-slate-900"
            type="text"
            placeholder="Username"
            value={username}
            onChange={(event) => setUsername(event.target.value)}
            required
          />
        </div>

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
          {loading ? "Creating..." : "Create Account"}
        </button>

        <p className="text-sm text-slate-600 dark:text-slate-300">
          Already have an account? <Link className="text-william-electric underline" to="/login">Sign in</Link>
        </p>
      </form>
    </div>
  );
}
