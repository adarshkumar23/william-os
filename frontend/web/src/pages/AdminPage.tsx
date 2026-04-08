import { useEffect, useState } from "react";

import { AppCard, InsightBanner, SkeletonLoader } from "../components/ui";
import { useAuth } from "../contexts/AuthContext";
import { api } from "../services/api";
import { AdminStats, AdminUser } from "../types/api";

export default function AdminPage() {
  const { user } = useAuth();
  const [stats, setStats] = useState<AdminStats | null>(null);
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [inviteEmail, setInviteEmail] = useState("");
  const [inviteRole, setInviteRole] = useState<"family" | "guest">("family");
  const [inviteResult, setInviteResult] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const isOwner = String(user?.role || "") === "owner";

  const loadAdminData = async () => {
    setLoading(true);
    setError("");
    try {
      const [statsPayload, usersPayload] = await Promise.all([
        api.auth.adminStats(),
        api.auth.adminUsers(),
      ]);
      setStats(statsPayload as AdminStats);
      setUsers(usersPayload as AdminUser[]);
    } catch {
      setError("Failed to load admin data.");
      setStats(null);
      setUsers([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (!isOwner) {
      setLoading(false);
      return;
    }
    void loadAdminData();
  }, [isOwner]);

  const updateUser = async (targetUserId: string, patch: { role?: string; is_active?: boolean }) => {
    try {
      await api.auth.adminUpdateUser(targetUserId, patch);
      await loadAdminData();
    } catch {
      setError("Failed to update user.");
    }
  };

  const deactivateUser = async (targetUserId: string) => {
    try {
      await api.auth.adminDeactivateUser(targetUserId);
      await loadAdminData();
    } catch {
      setError("Failed to deactivate user.");
    }
  };

  const inviteFamily = async () => {
    setInviteResult("");
    try {
      const payload = await api.auth.inviteFamily({ email: inviteEmail, role: inviteRole });
      const inviteLink = (payload as Record<string, unknown>).invite_link;
      setInviteResult(String(inviteLink || "Invite generated"));
      setInviteEmail("");
    } catch {
      setInviteResult("Failed to create invite.");
    }
  };

  if (!isOwner) {
    return (
      <div className="space-y-4">
        <h1 className="text-2xl font-bold">Admin</h1>
        <InsightBanner text="Owner access required for this page." type="warning" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-bold">Admin</h1>
        <p className="text-sm text-text-secondary">Manage users, roles, and family invites.</p>
      </header>

      {error ? <InsightBanner text={error} type="danger" /> : null}

      <section className="grid gap-4 md:grid-cols-3">
        {loading ? (
          <SkeletonLoader variant="card" />
        ) : (
          <>
            <AppCard>
              <p className="meta-copy">Total users</p>
              <p className="mt-2 text-2xl font-semibold text-text-primary">{stats?.total_users ?? 0}</p>
            </AppCard>
            <AppCard>
              <p className="meta-copy">Active users</p>
              <p className="mt-2 text-2xl font-semibold text-text-primary">{stats?.active_users ?? 0}</p>
            </AppCard>
            <AppCard>
              <p className="meta-copy">New this week</p>
              <p className="mt-2 text-2xl font-semibold text-text-primary">{stats?.new_this_week ?? 0}</p>
            </AppCard>
          </>
        )}
      </section>

      <section className="grid gap-4 xl:grid-cols-3">
        <AppCard className="xl:col-span-2">
          <div className="mb-3 flex items-center justify-between">
            <h2 className="text-lg font-semibold">Users</h2>
            <button
              type="button"
              onClick={() => void loadAdminData()}
              className="rounded-lg border border-border px-3 py-1.5 text-xs"
            >
              Refresh
            </button>
          </div>
          <div className="space-y-2">
            {loading ? (
              <SkeletonLoader variant="text" lines={6} />
            ) : users.length === 0 ? (
              <p className="text-sm text-text-secondary">No users found.</p>
            ) : (
              users.map((member) => (
                <div key={member.id} className="rounded-lg border border-border bg-surface-raised p-3">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div>
                      <p className="text-sm font-semibold text-text-primary">{member.full_name}</p>
                      <p className="text-xs text-text-secondary">{member.email}</p>
                    </div>
                    <div className="flex items-center gap-2">
                      <select
                        value={member.role}
                        onChange={(event) => void updateUser(member.id, { role: event.target.value })}
                        className="rounded-lg border border-border bg-surface px-2 py-1 text-xs"
                      >
                        <option value="owner">owner</option>
                        <option value="family">family</option>
                        <option value="guest">guest</option>
                      </select>
                      <button
                        type="button"
                        onClick={() =>
                          void updateUser(member.id, {
                            is_active: !member.is_active,
                          })
                        }
                        className="rounded-lg border border-border px-2 py-1 text-xs"
                      >
                        {member.is_active ? "Deactivate" : "Activate"}
                      </button>
                      <button
                        type="button"
                        onClick={() => void deactivateUser(member.id)}
                        className="rounded-lg border border-danger/30 px-2 py-1 text-xs text-danger"
                      >
                        Disable
                      </button>
                    </div>
                  </div>
                </div>
              ))
            )}
          </div>
        </AppCard>

        <AppCard>
          <h2 className="text-lg font-semibold">Invite Family</h2>
          <p className="mt-1 text-sm text-text-secondary">Generate invite links for shared household members.</p>
          <div className="mt-3 space-y-2">
            <input
              value={inviteEmail}
              onChange={(event) => setInviteEmail(event.target.value)}
              placeholder="email@example.com"
              className="w-full rounded-lg border border-border bg-surface px-3 py-2 text-sm"
            />
            <select
              value={inviteRole}
              onChange={(event) => setInviteRole(event.target.value as "family" | "guest")}
              className="w-full rounded-lg border border-border bg-surface px-3 py-2 text-sm"
            >
              <option value="family">family</option>
              <option value="guest">guest</option>
            </select>
            <button
              type="button"
              onClick={() => void inviteFamily()}
              className="w-full rounded-lg bg-accent px-3 py-2 text-sm font-semibold text-white"
            >
              Create invite
            </button>
            {inviteResult ? (
              <p className="rounded-lg border border-border bg-surface-raised p-2 text-xs text-text-secondary break-all">
                {inviteResult}
              </p>
            ) : null}
          </div>
        </AppCard>
      </section>
    </div>
  );
}
