import { useEffect, useMemo, useState } from "react";
import { Download, Smartphone, ShieldCheck, UserRound } from "lucide-react";

import { useAuth } from "../contexts/AuthContext";
import { api } from "../services/api";

function triggerDownload(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
  URL.revokeObjectURL(url);
}

export default function SettingsPage() {
  const { user, logout } = useAuth();
  const [profileDraft, setProfileDraft] = useState({
    full_name: "",
    username: "",
    timezone: "",
    wake_time: "06:30",
    sleep_time: "22:30",
  });
  const [telegramStatus, setTelegramStatus] = useState<Record<string, unknown> | null>(null);
  const [linkedCode, setLinkedCode] = useState("");

  useEffect(() => {
    if (!user) {
      return;
    }
    setProfileDraft({
      full_name: String(user.full_name ?? ""),
      username: String(user.username ?? ""),
      timezone: String(user.timezone ?? "UTC"),
      wake_time: String(user.wake_time ?? "06:30"),
      sleep_time: String(user.sleep_time ?? "22:30"),
    });
  }, [user]);

  useEffect(() => {
    void api.messaging.telegramStatus().then(setTelegramStatus).catch(() => setTelegramStatus(null));
  }, []);

  const connected = useMemo(() => Boolean(telegramStatus && telegramStatus.connected), [telegramStatus]);

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-bold">Settings</h1>
        <p className="text-sm text-[rgb(var(--text-dim))]">Identity, integrations, security, and data export controls.</p>
      </header>

      <section className="grid gap-4 xl:grid-cols-2">
        <article className="card p-4">
          <div className="mb-3 flex items-center gap-2">
            <UserRound className="h-4 w-4 text-[rgb(var(--primary))]" />
            <h2 className="text-lg font-semibold">Profile</h2>
          </div>
          <div className="grid gap-3 sm:grid-cols-2">
            <label className="space-y-1">
              <span className="text-sm">Full name</span>
              <input
                value={profileDraft.full_name}
                onChange={(event) => setProfileDraft((prev) => ({ ...prev, full_name: event.target.value }))}
                className="w-full rounded-xl border border-[rgb(var(--border))] bg-[rgb(var(--bg-muted))] px-3 py-2"
              />
            </label>
            <label className="space-y-1">
              <span className="text-sm">Username</span>
              <input
                value={profileDraft.username}
                onChange={(event) => setProfileDraft((prev) => ({ ...prev, username: event.target.value }))}
                className="w-full rounded-xl border border-[rgb(var(--border))] bg-[rgb(var(--bg-muted))] px-3 py-2"
              />
            </label>
            <label className="space-y-1">
              <span className="text-sm">Timezone</span>
              <input
                value={profileDraft.timezone}
                onChange={(event) => setProfileDraft((prev) => ({ ...prev, timezone: event.target.value }))}
                className="w-full rounded-xl border border-[rgb(var(--border))] bg-[rgb(var(--bg-muted))] px-3 py-2"
              />
            </label>
            <label className="space-y-1">
              <span className="text-sm">Wake / Sleep</span>
              <div className="grid grid-cols-2 gap-2">
                <input
                  value={profileDraft.wake_time}
                  onChange={(event) => setProfileDraft((prev) => ({ ...prev, wake_time: event.target.value }))}
                  className="w-full rounded-xl border border-[rgb(var(--border))] bg-[rgb(var(--bg-muted))] px-3 py-2"
                />
                <input
                  value={profileDraft.sleep_time}
                  onChange={(event) => setProfileDraft((prev) => ({ ...prev, sleep_time: event.target.value }))}
                  className="w-full rounded-xl border border-[rgb(var(--border))] bg-[rgb(var(--bg-muted))] px-3 py-2"
                />
              </div>
            </label>
          </div>
          <p className="mt-3 text-xs text-[rgb(var(--text-dim))]">Profile updates are local until backend profile patch endpoint is added.</p>
        </article>

        <article className="card p-4">
          <div className="mb-3 flex items-center gap-2">
            <Smartphone className="h-4 w-4 text-[rgb(var(--primary))]" />
            <h2 className="text-lg font-semibold">Telegram integration</h2>
          </div>

          <div className="rounded-xl bg-[rgb(var(--bg-muted))] p-3 text-sm">
            <p>
              Status: <span className={connected ? "text-emerald-400" : "text-amber-400"}>{connected ? "Connected" : "Not linked"}</span>
            </p>
            <p className="mt-1 text-xs text-[rgb(var(--text-dim))]">Use linking code from Telegram bot to connect this account.</p>
          </div>

          <div className="mt-3 flex gap-2">
            <input
              value={linkedCode}
              onChange={(event) => setLinkedCode(event.target.value)}
              placeholder="Linking code"
              className="flex-1 rounded-xl border border-[rgb(var(--border))] bg-[rgb(var(--bg-muted))] px-3 py-2"
            />
            <button
              type="button"
              onClick={() =>
                void api.messaging
                  .linkTelegram({ linking_code: linkedCode })
                  .then(() => api.messaging.telegramStatus())
                  .then(setTelegramStatus)
              }
              className="rounded-xl bg-[rgb(var(--primary))] px-3 py-2 text-sm font-semibold text-white"
            >
              Link
            </button>
            <button
              type="button"
              onClick={() => void api.messaging.unlinkTelegram().then(() => setTelegramStatus(null))}
              className="rounded-xl border border-[rgb(var(--border))] px-3 py-2 text-sm"
            >
              Unlink
            </button>
          </div>
        </article>
      </section>

      <section className="grid gap-4 xl:grid-cols-2">
        <article className="card p-4">
          <div className="mb-3 flex items-center gap-2">
            <Download className="h-4 w-4 text-[rgb(var(--primary))]" />
            <h2 className="text-lg font-semibold">Data export</h2>
          </div>
          <div className="grid gap-2 sm:grid-cols-3">
            <button
              type="button"
              className="rounded-xl border border-[rgb(var(--border))] bg-[rgb(var(--bg-muted))] px-3 py-2 text-sm"
              onClick={() => void api.export.full().then((blob) => triggerDownload(blob, "william-full-export.zip"))}
            >
              Full export
            </button>
            <button
              type="button"
              className="rounded-xl border border-[rgb(var(--border))] bg-[rgb(var(--bg-muted))] px-3 py-2 text-sm"
              onClick={() => void api.export.journal("journal-passphrase").then((blob) => triggerDownload(blob, "journal-export.zip"))}
            >
              Journal export
            </button>
            <button
              type="button"
              className="rounded-xl border border-[rgb(var(--border))] bg-[rgb(var(--bg-muted))] px-3 py-2 text-sm"
              onClick={() => void api.export.lifetime("lifetime-passphrase").then((blob) => triggerDownload(blob, "lifetime-export.zip"))}
            >
              Lifetime export
            </button>
          </div>
        </article>

        <article className="card p-4">
          <div className="mb-3 flex items-center gap-2">
            <ShieldCheck className="h-4 w-4 text-[rgb(var(--primary))]" />
            <h2 className="text-lg font-semibold">Security</h2>
          </div>
          <p className="text-sm text-[rgb(var(--text-dim))]">Session managed via access and refresh tokens with automatic renewal.</p>
          <div className="mt-3 flex gap-2">
            <button
              type="button"
              onClick={() => void logout()}
              className="rounded-xl bg-[rgb(var(--danger))] px-3 py-2 text-sm font-semibold text-white"
            >
              Log out
            </button>
            <button
              type="button"
              onClick={() =>
                void api.export
                  .deleteAccount("confirm-account-delete")
                  .then(() => logout())
                  .catch(() => undefined)
              }
              className="rounded-xl border border-[rgb(var(--danger))]/40 px-3 py-2 text-sm text-[rgb(var(--danger))]"
            >
              Delete account
            </button>
          </div>
        </article>
      </section>
    </div>
  );
}
