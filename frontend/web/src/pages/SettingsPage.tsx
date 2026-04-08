import { useEffect, useMemo, useState } from "react";
import { Clock3, Download, KeyRound, ShieldCheck, ShieldQuestion, Smartphone, UserRound } from "lucide-react";
import { Link } from "react-router-dom";

import { useAuth } from "../contexts/AuthContext";
import { api } from "../services/api";
import { CalendarSyncConflict } from "../types/api";

function triggerDownload(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
  URL.revokeObjectURL(url);
}

export default function SettingsPage() {
  const { user, logout, refreshUser } = useAuth();
  const [profileDraft, setProfileDraft] = useState({
    full_name: "",
    display_name: "",
    avatar_url: "",
    timezone: "",
    wake_time: "06:30",
    sleep_time: "22:30",
    sleep_goal: "8",
  });
  const [savingProfile, setSavingProfile] = useState(false);
  const [profileMessage, setProfileMessage] = useState("");
  const [telegramStatus, setTelegramStatus] = useState<Record<string, unknown> | null>(null);
  const [linkedCode, setLinkedCode] = useState("");
  const [totpCode, setTotpCode] = useState("");
  const [totpSetup, setTotpSetup] = useState<Record<string, string> | null>(null);
  const [sessions, setSessions] = useState<Array<Record<string, unknown>>>([]);
  const [loginHistory, setLoginHistory] = useState<Array<Record<string, unknown>>>([]);
  const [secrets, setSecrets] = useState<Array<Record<string, unknown>>>([]);
  const [calendarConflicts, setCalendarConflicts] = useState<CalendarSyncConflict[]>([]);
  const [calendarMessage, setCalendarMessage] = useState("");
  const [reportDays, setReportDays] = useState("30");
  const [secretProvider, setSecretProvider] = useState("openrouter");
  const [secretValue, setSecretValue] = useState("");

  useEffect(() => {
    if (!user) {
      return;
    }
    setProfileDraft({
      full_name: String(user.full_name ?? ""),
      display_name: String(user.display_name ?? ""),
      avatar_url: String(user.avatar_url ?? ""),
      timezone: String(user.timezone ?? "UTC"),
      wake_time: String(user.wake_time ?? "06:30"),
      sleep_time: String(user.sleep_time ?? "22:30"),
      sleep_goal: String(user.sleep_goal ?? 8),
    });
  }, [user]);

  useEffect(() => {
    void api.messaging.telegramStatus().then(setTelegramStatus).catch(() => setTelegramStatus(null));
  }, []);

  const refreshSecurityData = async () => {
    try {
      const [sessionRows, historyRows, secretRows] = await Promise.all([
        api.auth.sessions(),
        api.auth.loginHistory(),
        api.security.listSecrets(),
      ]);
      setSessions(sessionRows as Array<Record<string, unknown>>);
      setLoginHistory(historyRows as Array<Record<string, unknown>>);
      setSecrets(secretRows as Array<Record<string, unknown>>);
    } catch {
      setSessions([]);
      setLoginHistory([]);
      setSecrets([]);
    }
  };

  useEffect(() => {
    void refreshSecurityData();
  }, []);

  useEffect(() => {
    void api.calendar
      .syncConflicts()
      .then((payload) => setCalendarConflicts(payload.conflicts ?? []))
      .catch(() => setCalendarConflicts([]));
  }, []);

  const saveProfile = async () => {
    setSavingProfile(true);
    setProfileMessage("");
    try {
      await api.auth.updateProfile({
        full_name: profileDraft.full_name,
        display_name: profileDraft.display_name || null,
        avatar_url: profileDraft.avatar_url || null,
        timezone: profileDraft.timezone,
        wake_time: profileDraft.wake_time,
        sleep_time: profileDraft.sleep_time,
        sleep_goal: Number(profileDraft.sleep_goal || 8),
      });
      await refreshUser();
      setProfileMessage("Profile saved.");
    } catch {
      setProfileMessage("Failed to save profile.");
    } finally {
      setSavingProfile(false);
    }
  };

  const runGoogleToWilliamSync = async () => {
    try {
      const payload = await api.calendar.syncGoogleToWilliam();
      setCalendarMessage(`Google to William sync complete (${String(payload.synced ?? 0)} synced).`);
      const conflicts = await api.calendar.syncConflicts();
      setCalendarConflicts(conflicts.conflicts ?? []);
    } catch {
      setCalendarMessage("Google to William sync failed.");
    }
  };

  const runWilliamToGoogleSync = async () => {
    try {
      const payload = await api.calendar.syncWilliamToGoogle();
      setCalendarMessage(`William to Google sync complete (${String(payload.pushed ?? 0)} pushed).`);
      const conflicts = await api.calendar.syncConflicts();
      setCalendarConflicts(conflicts.conflicts ?? []);
    } catch {
      setCalendarMessage("William to Google sync failed.");
    }
  };

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
              <span className="text-sm">Display name</span>
              <input
                value={profileDraft.display_name}
                onChange={(event) => setProfileDraft((prev) => ({ ...prev, display_name: event.target.value }))}
                className="w-full rounded-xl border border-[rgb(var(--border))] bg-[rgb(var(--bg-muted))] px-3 py-2"
              />
            </label>
            <label className="space-y-1">
              <span className="text-sm">Avatar URL</span>
              <input
                value={profileDraft.avatar_url}
                onChange={(event) => setProfileDraft((prev) => ({ ...prev, avatar_url: event.target.value }))}
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
            <label className="space-y-1">
              <span className="text-sm">Sleep goal (hours)</span>
              <input
                value={profileDraft.sleep_goal}
                onChange={(event) => setProfileDraft((prev) => ({ ...prev, sleep_goal: event.target.value }))}
                className="w-full rounded-xl border border-[rgb(var(--border))] bg-[rgb(var(--bg-muted))] px-3 py-2"
              />
            </label>
          </div>
          <div className="mt-3 flex items-center gap-2">
            <button
              type="button"
              onClick={() => void saveProfile()}
              disabled={savingProfile}
              className="rounded-xl bg-[rgb(var(--primary))] px-3 py-2 text-sm font-semibold text-white disabled:opacity-40"
            >
              {savingProfile ? "Saving..." : "Save profile"}
            </button>
            {profileMessage ? <p className="text-xs text-[rgb(var(--text-dim))]">{profileMessage}</p> : null}
          </div>
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
            <ShieldCheck className="h-4 w-4 text-[rgb(var(--primary))]" />
            <h2 className="text-lg font-semibold">Power User</h2>
          </div>
          <p className="text-sm text-[rgb(var(--text-dim))]">
            Configure personal automations in the Rules Engine.
          </p>
          <Link
            to="/rules"
            className="mt-3 inline-flex rounded-xl border border-[rgb(var(--border))] bg-[rgb(var(--bg-muted))] px-3 py-2 text-sm font-medium"
          >
            Open Rules Engine
          </Link>
        </article>

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
          <div className="mt-3 grid gap-2 sm:grid-cols-3">
            <button
              type="button"
              className="rounded-xl border border-[rgb(var(--border))] bg-[rgb(var(--bg-muted))] px-3 py-2 text-sm"
              onClick={() => void api.export.weeklyReportPdf().then((blob) => triggerDownload(blob, "weekly-report.pdf"))}
            >
              Weekly PDF
            </button>
            <button
              type="button"
              className="rounded-xl border border-[rgb(var(--border))] bg-[rgb(var(--bg-muted))] px-3 py-2 text-sm"
              onClick={() => void api.export.monthlyReportPdf().then((blob) => triggerDownload(blob, "monthly-report.pdf"))}
            >
              Monthly PDF
            </button>
            <div className="flex items-center gap-2">
              <input
                value={reportDays}
                onChange={(event) => setReportDays(event.target.value)}
                className="w-16 rounded-xl border border-[rgb(var(--border))] bg-[rgb(var(--bg-muted))] px-2 py-2 text-sm"
              />
              <button
                type="button"
                className="rounded-xl border border-[rgb(var(--border))] bg-[rgb(var(--bg-muted))] px-3 py-2 text-sm"
                onClick={() =>
                  void api.export
                    .customReportPdf(Number(reportDays || 30))
                    .then((blob) => triggerDownload(blob, `custom-report-${reportDays}d.pdf`))
                }
              >
                Custom PDF
              </button>
            </div>
          </div>
        </article>

        <article className="card p-4">
          <div className="mb-3 flex items-center gap-2">
            <Clock3 className="h-4 w-4 text-[rgb(var(--primary))]" />
            <h2 className="text-lg font-semibold">Calendar sync</h2>
          </div>
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              onClick={() => void runGoogleToWilliamSync()}
              className="rounded-xl border border-[rgb(var(--border))] px-3 py-2 text-sm"
            >
              Sync Google -> William
            </button>
            <button
              type="button"
              onClick={() => void runWilliamToGoogleSync()}
              className="rounded-xl border border-[rgb(var(--border))] px-3 py-2 text-sm"
            >
              Sync William -> Google
            </button>
          </div>
          {calendarMessage ? <p className="mt-2 text-xs text-[rgb(var(--text-dim))]">{calendarMessage}</p> : null}
          <div className="mt-3 space-y-2 text-sm">
            {calendarConflicts.length === 0 ? (
              <p className="text-[rgb(var(--text-dim))]">No sync conflicts detected.</p>
            ) : (
              calendarConflicts.slice(0, 6).map((conflict, index) => (
                <div key={`${String(conflict.william_block || index)}`} className="rounded-xl border border-[rgb(var(--border))] p-2">
                  <p className="font-medium">{String(conflict.william_block || "William block")}</p>
                  <p className="text-xs text-[rgb(var(--text-dim))]">Conflicts with: {String(conflict.google_event || "Google event")}</p>
                  <p className="text-xs text-[rgb(var(--text-dim))]">Overlap: {String(conflict.overlap_minutes || 0)} min</p>
                </div>
              ))
            )}
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

          <div className="mt-6 space-y-3 rounded-xl border border-[rgb(var(--border))] p-3">
            <div className="flex items-center gap-2">
              <ShieldQuestion className="h-4 w-4 text-[rgb(var(--primary))]" />
              <h3 className="text-sm font-semibold">Two-factor authentication</h3>
            </div>

            {totpSetup ? (
              <div className="space-y-2">
                <img src={String(totpSetup.qr_code_data_url || "")} alt="2FA QR code" className="h-40 w-40 rounded-lg border border-[rgb(var(--border))] bg-white p-2" />
                <p className="text-xs text-[rgb(var(--text-dim))]">
                  Secret preview: {String(totpSetup.secret_preview || "")}
                </p>
                <div className="flex gap-2">
                  <input
                    value={totpCode}
                    onChange={(event) => setTotpCode(event.target.value)}
                    placeholder="Enter app code"
                    className="flex-1 rounded-xl border border-[rgb(var(--border))] bg-[rgb(var(--bg-muted))] px-3 py-2"
                  />
                  <button
                    type="button"
                    onClick={() =>
                      void api.auth.verify2fa(totpCode).then(() => {
                        setTotpSetup(null);
                        setTotpCode("");
                      })
                    }
                    className="rounded-xl bg-[rgb(var(--primary))] px-3 py-2 text-sm font-semibold text-white"
                  >
                    Verify
                  </button>
                </div>
              </div>
            ) : (
              <button
                type="button"
                onClick={() => void api.auth.setup2fa().then((payload) => setTotpSetup(payload as Record<string, string>))}
                className="rounded-xl border border-[rgb(var(--border))] px-3 py-2 text-sm"
              >
                Enable 2FA
              </button>
            )}
          </div>
        </article>
      </section>

      <section className="grid gap-4 xl:grid-cols-2">
        <article className="card p-4">
          <div className="mb-3 flex items-center gap-2">
            <Smartphone className="h-4 w-4 text-[rgb(var(--primary))]" />
            <h2 className="text-lg font-semibold">Active sessions</h2>
          </div>
          <div className="space-y-2 text-sm">
            {sessions.length === 0 ? (
              <p className="text-[rgb(var(--text-dim))]">No active sessions found.</p>
            ) : (
              sessions.map((session) => (
                <div key={String(session.id)} className="rounded-xl border border-[rgb(var(--border))] p-3">
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="font-medium">{String(session.device_name || "Unknown device")}</p>
                      <p className="text-xs text-[rgb(var(--text-dim))]">{String(session.device_type || "web")} • {String(session.last_active || "unknown")}</p>
                    </div>
                    <button
                      type="button"
                      disabled={Boolean(session.is_current)}
                      onClick={() => void api.auth.revokeSession(String(session.id)).then(() => refreshSecurityData())}
                      className="rounded-xl border border-[rgb(var(--border))] px-3 py-1.5 text-xs disabled:opacity-40"
                    >
                      {session.is_current ? "Current" : "Revoke"}
                    </button>
                  </div>
                </div>
              ))
            )}
          </div>
        </article>

        <article className="card p-4">
          <div className="mb-3 flex items-center gap-2">
            <Clock3 className="h-4 w-4 text-[rgb(var(--primary))]" />
            <h2 className="text-lg font-semibold">Recent login history</h2>
          </div>
          <div className="space-y-2 text-sm">
            {loginHistory.length === 0 ? (
              <p className="text-[rgb(var(--text-dim))]">No login activity yet.</p>
            ) : (
              loginHistory.slice(0, 8).map((item) => (
                <div key={String(item.id)} className="rounded-xl border border-[rgb(var(--border))] p-2">
                  <p className="font-medium">
                    {item.success ? "Successful login" : "Failed login"}
                  </p>
                  <p className="text-xs text-[rgb(var(--text-dim))]">
                    {String(item.timestamp || "")} • {String(item.ip || "unknown ip")} • {String(item.country || "unknown country")}
                  </p>
                </div>
              ))
            )}
          </div>
        </article>
      </section>

      <section className="grid gap-4 xl:grid-cols-2">
        <article className="card p-4">
          <div className="mb-3 flex items-center gap-2">
            <KeyRound className="h-4 w-4 text-[rgb(var(--primary))]" />
            <h2 className="text-lg font-semibold">API secret rotation</h2>
          </div>
          <div className="grid gap-2 sm:grid-cols-3">
            <input
              value={secretProvider}
              onChange={(event) => setSecretProvider(event.target.value)}
              placeholder="provider"
              className="rounded-xl border border-[rgb(var(--border))] bg-[rgb(var(--bg-muted))] px-3 py-2"
            />
            <input
              value={secretValue}
              onChange={(event) => setSecretValue(event.target.value)}
              placeholder="new secret"
              className="rounded-xl border border-[rgb(var(--border))] bg-[rgb(var(--bg-muted))] px-3 py-2"
            />
            <button
              type="button"
              onClick={() =>
                void api.security.rotateSecret({ provider: secretProvider, plaintext_key: secretValue }).then(() => {
                  setSecretValue("");
                  refreshSecurityData();
                })
              }
              className="rounded-xl bg-[rgb(var(--primary))] px-3 py-2 text-sm font-semibold text-white"
            >
              Rotate
            </button>
          </div>

          <div className="mt-3 space-y-2 text-xs">
            {secrets.map((secret) => (
              <div key={String(secret.id)} className="flex items-center justify-between rounded-xl border border-[rgb(var(--border))] px-3 py-2">
                <span>{String(secret.provider)} ({String(secret.key_hint)}) v{String(secret.version)}</span>
                <button
                  type="button"
                  onClick={() => void api.security.revokeSecret(String(secret.id)).then(() => refreshSecurityData())}
                  className="rounded-lg border border-[rgb(var(--border))] px-2 py-1"
                >
                  Revoke
                </button>
              </div>
            ))}
          </div>
        </article>
      </section>

      <section className="card p-4">
        <h2 className="text-lg font-semibold">Compliance export</h2>
        <p className="text-sm text-[rgb(var(--text-dim))]">Download an audit-trail CSV for investigations and compliance reviews.</p>
        <button
          type="button"
          className="mt-3 rounded-xl border border-[rgb(var(--border))] bg-[rgb(var(--bg-muted))] px-3 py-2 text-sm"
          onClick={() => void api.export.auditCsv().then((blob) => triggerDownload(blob, "audit-log.csv"))}
        >
          Download audit CSV
        </button>
      </section>

      <section className="card p-4">
        <h2 className="text-lg font-semibold">Connected Accounts</h2>
        <p className="text-sm text-[rgb(var(--text-dim))] mb-4">Connect your calendars to William OS.</p>
        <div className="space-y-4">
          <div className="flex items-center justify-between rounded-xl border border-[rgb(var(--border))] px-4 py-3">
            <div>
              <p className="font-medium">Google Calendar</p>
              <p className="text-xs text-[rgb(var(--text-dim))]">Sync your Google Calendar events</p>
            </div>
            
            <a
              href="/api/v1/calendar/google/auth-url"
              onClick={async (e) => {
                e.preventDefault();
                const res = await fetch('/api/v1/calendar/google/auth-url', { headers: { Authorization: `Bearer ${localStorage.getItem('william_access_token')}` } });
                const data = await res.json();
                if (data.auth_url) { window.location.href = data.auth_url; } else { alert('Error: ' + JSON.stringify(data)); }
              }}
              className="rounded-xl bg-blue-600 px-4 py-2 text-sm text-white hover:bg-blue-700"
            >
              Connect
            </a>
          </div>
          <div className="rounded-xl border border-[rgb(var(--border))] px-4 py-3">
            <div className="mb-3">
              <p className="font-medium">Apple Calendar</p>
              <p className="text-xs text-[rgb(var(--text-dim))]">Connect via iCloud CalDAV</p>
            </div>
            <div className="space-y-2">
              <input id="apple-id" type="email" placeholder="Apple ID (iCloud email)" className="w-full rounded-lg border border-[rgb(var(--border))] bg-[rgb(var(--bg-muted))] px-3 py-2 text-sm" />
              <input id="apple-pass" type="password" placeholder="App-specific password" className="w-full rounded-lg border border-[rgb(var(--border))] bg-[rgb(var(--bg-muted))] px-3 py-2 text-sm" />
              <button
                type="button"
                onClick={async () => {
                  const appleId = (document.getElementById('apple-id') as HTMLInputElement).value;
                  const appPass = (document.getElementById('apple-pass') as HTMLInputElement).value;
                  const res = await fetch('/api/v1/calendar/apple/connect', { method: 'POST', headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${localStorage.getItem('william_access_token')}` }, body: JSON.stringify({ apple_id: appleId, app_password: appPass }) });
                  const data = await res.json();
                  alert(data.status === 'connected' ? 'Apple Calendar connected!' : 'Failed: ' + JSON.stringify(data));
                }}
                className="rounded-xl bg-gray-700 px-4 py-2 text-sm text-white hover:bg-gray-600"
              >
                Connect Apple Calendar
              </button>
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}
