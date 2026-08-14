"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import {
  FileText,
  Loader2,
  MessageSquareText,
  RefreshCw,
  Shield,
  ThumbsUp,
  Users,
} from "lucide-react";

import { RequireAuth } from "@/components/require-auth";
import { SiteHeader } from "@/components/site-header";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { ApiError } from "@/lib/api";
import {
  type AdminDocument,
  type AdminStats,
  type AdminUser,
  type Role,
  getAdminStats,
  listAdminDocuments,
  listAdminUsers,
  updateUserRole,
} from "@/lib/admin";
import { useAuth } from "@/lib/auth";
import { formatDate } from "@/lib/documents";
import { cn } from "@/lib/utils";

/* ─── Role Badge ─── */

const roleColors: Record<Role, string> = {
  STUDENT:
    "border-[var(--info)] bg-[var(--info-faint)] text-[var(--info)]",
  FACULTY:
    "border-[var(--accent)] bg-[var(--accent-faint)] text-[var(--accent-hover)]",
  ADMIN:
    "border-[var(--ink)] bg-[var(--canvas-inset)] text-[var(--ink)]",
};

function RoleBadge({ role }: { role: Role }) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full border px-2.5 py-0.5 text-[11px] font-semibold uppercase tracking-wide",
        roleColors[role],
      )}
    >
      {role.charAt(0) + role.slice(1).toLowerCase()}
    </span>
  );
}

/* ─── Stat Card ─── */

function StatCard({
  icon,
  label,
  value,
  variant = "default",
}: {
  icon: React.ReactNode;
  label: string;
  value: number;
  variant?: "default" | "danger";
}) {
  return (
    <div
      className={cn(
        "rounded-[var(--radius-lg)] border p-5 shadow-[var(--shadow-sm)]",
        variant === "danger"
          ? "border-[var(--danger)] bg-[var(--danger-faint)]"
          : "border-[var(--edge)] bg-[var(--canvas-raised)]",
      )}
    >
      <div
        className={cn(
          "flex items-center gap-2",
          variant === "danger"
            ? "text-[var(--danger)]"
            : "text-[var(--ink-faint)]",
        )}
      >
        {icon}
        <span className="text-[11px] font-semibold uppercase tracking-[0.1em]">
          {label}
        </span>
      </div>
      <p
        className={cn(
          "mt-2 text-3xl",
          variant === "danger"
            ? "text-[var(--danger)] font-bold"
            : "text-[var(--ink)]",
        )}
        style={{ fontFamily: "var(--font-display)" }}
      >
        {value}
      </p>
    </div>
  );
}

/* ─── Admin Shell ─── */

function AdminShell() {
  const { user } = useAuth();
  const router = useRouter();

  const [users, setUsers] = useState<AdminUser[]>([]);
  const [documents, setDocuments] = useState<AdminDocument[]>([]);
  const [stats, setStats] = useState<AdminStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [changingRole, setChangingRole] = useState<string | null>(null);
  const [roleError, setRoleError] = useState<string | null>(null);

  useEffect(() => {
    if (user && user.role !== "ADMIN") {
      router.replace("/dashboard");
    }
  }, [user, router]);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [usersData, docsData, statsData] = await Promise.all([
        listAdminUsers(),
        listAdminDocuments(),
        getAdminStats(),
      ]);
      setUsers(usersData);
      setDocuments(docsData);
      setStats(statsData);
    } catch (err) {
      setError(
        err instanceof ApiError
          ? err.message
          : "Unable to load admin data. Admin access required.",
      );
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  async function handleRoleChange(id: string, role: Role) {
    setRoleError(null);
    setChangingRole(id);
    try {
      const updated = await updateUserRole(id, role);
      setUsers((current) =>
        current.map((u) => (u.id === id ? { ...u, role: updated.role } : u)),
      );
    } catch (err) {
      setRoleError(
        err instanceof ApiError ? err.message : "Unable to update role.",
      );
    } finally {
      setChangingRole(null);
    }
  }

  return (
    <div className="min-h-screen bg-[var(--canvas)] text-[var(--ink)]">
      <SiteHeader />

      <main className="mx-auto max-w-6xl space-y-8 px-5 py-10 sm:px-8 animate-page-in">
        {/* Header */}
        <section className="flex items-center justify-between">
          <div>
            <h1
              className="text-3xl tracking-tight"
              style={{ fontFamily: "var(--font-display)" }}
            >
              Admin
            </h1>
            <p className="mt-1.5 text-[var(--ink-faint)]">
              Manage users, roles and review document activity.
            </p>
          </div>
          <Button variant="outline" size="sm" onClick={refresh}>
            <RefreshCw className="h-3.5 w-3.5" aria-hidden />
            Refresh
          </Button>
        </section>

        {roleError && <Alert variant="error">{roleError}</Alert>}
        {error && <Alert variant="error">{error}</Alert>}

        {/* Loading */}
        {loading && (
          <div className="flex items-center gap-2.5 text-sm text-[var(--ink-faint)]">
            <Loader2
              className="h-4 w-4 text-[var(--accent)]"
              style={{ animation: "spin 0.7s linear infinite" }}
              aria-hidden
            />
            Loading admin data…
          </div>
        )}

        {/* Stats */}
        {!loading && stats && (
          <section className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            <StatCard
              icon={<Users className="h-4 w-4" aria-hidden />}
              label="Users"
              value={stats.users}
            />
            <StatCard
              icon={<FileText className="h-4 w-4" aria-hidden />}
              label="Documents"
              value={stats.documents}
            />
            <StatCard
              icon={<MessageSquareText className="h-4 w-4" aria-hidden />}
              label="Conversations"
              value={stats.conversations}
            />
            <StatCard
              icon={<Shield className="h-4 w-4" aria-hidden />}
              label="Active documents"
              value={stats.active_documents}
            />
            <StatCard
              icon={<ThumbsUp className="h-4 w-4" aria-hidden />}
              label="Feedback entries"
              value={stats.feedback_entries}
            />
            <StatCard
              icon={<FileText className="h-4 w-4" aria-hidden />}
              label="Failed documents"
              value={stats.failed_documents}
              variant="danger"
            />
          </section>
        )}

        {/* Users & Documents */}
        {!loading && (
          <>
            {/* Users */}
            <section>
              <div className="flex items-center gap-2.5">
                <Users className="h-4 w-4 text-[var(--accent)]" aria-hidden />
                <h2
                  className="text-lg text-[var(--ink)]"
                  style={{ fontFamily: "var(--font-display)" }}
                >
                  Users
                </h2>
                <span className="rounded-full bg-[var(--canvas-inset)] px-2 py-0.5 text-xs font-semibold text-[var(--ink-faint)]">
                  {users.length}
                </span>
              </div>
              <ul className="mt-4 space-y-2">
                {users.map((adminUser) => (
                  <li
                    key={adminUser.id}
                    className="flex flex-wrap items-center justify-between gap-3 rounded-[var(--radius-lg)] border border-[var(--edge)] bg-[var(--canvas-raised)] p-4 shadow-[var(--shadow-sm)]"
                  >
                    <div className="min-w-0">
                      <p className="font-semibold text-[var(--ink)]">
                        {adminUser.name}
                        {adminUser.id === user?.id && (
                          <span className="ml-2 text-xs font-normal text-[var(--ink-ghost)]">
                            (you)
                          </span>
                        )}
                      </p>
                      <p className="text-sm text-[var(--ink-faint)]">
                        {adminUser.email}
                      </p>
                    </div>
                    <div className="flex items-center gap-3">
                      <RoleBadge role={adminUser.role} />
                      <select
                        value={adminUser.role}
                        disabled={changingRole === adminUser.id}
                        onChange={(e) =>
                          handleRoleChange(
                            adminUser.id,
                            e.target.value as Role,
                          )
                        }
                        className="h-8 rounded-[var(--radius-sm)] border border-[var(--edge-strong)] bg-[var(--canvas-raised)] px-2 text-xs text-[var(--ink-muted)] transition-colors duration-150 focus:border-[var(--accent)] focus:outline-none focus:ring-2 focus:ring-[var(--accent)]/25"
                        aria-label={`Change role for ${adminUser.name}`}
                      >
                        <option value="STUDENT">Student</option>
                        <option value="FACULTY">Faculty</option>
                        <option value="ADMIN">Admin</option>
                      </select>
                      {changingRole === adminUser.id && (
                        <Loader2
                          className="h-4 w-4 text-[var(--accent)]"
                          style={{ animation: "spin 0.7s linear infinite" }}
                          aria-hidden
                        />
                      )}
                    </div>
                  </li>
                ))}
              </ul>
            </section>

            {/* Documents */}
            <section>
              <div className="flex items-center gap-2.5">
                <FileText
                  className="h-4 w-4 text-[var(--accent)]"
                  aria-hidden
                />
                <h2
                  className="text-lg text-[var(--ink)]"
                  style={{ fontFamily: "var(--font-display)" }}
                >
                  Documents
                </h2>
                <span className="rounded-full bg-[var(--canvas-inset)] px-2 py-0.5 text-xs font-semibold text-[var(--ink-faint)]">
                  {documents.length}
                </span>
              </div>
              <ul className="mt-4 space-y-2">
                {documents.map((doc) => (
                  <li
                    key={doc.id}
                    className="flex flex-wrap items-center justify-between gap-3 rounded-[var(--radius-lg)] border border-[var(--edge)] bg-[var(--canvas-raised)] p-4 shadow-[var(--shadow-sm)] border-l-[3px] border-l-[var(--accent-muted)]"
                  >
                    <div className="min-w-0">
                      <p className="font-semibold text-[var(--ink)]">
                        {doc.title}
                      </p>
                      <p className="text-sm text-[var(--ink-faint)]">
                        Uploaded by {doc.owner_name ?? "Unknown"} ·{" "}
                        {formatDate(doc.created_at)}
                        {doc.page_count != null &&
                          ` · ${doc.page_count} page${doc.page_count === 1 ? "" : "s"}`}
                      </p>
                    </div>
                    <div className="flex shrink-0 items-center gap-2 text-xs">
                      <span className="rounded-full border border-[var(--edge)] bg-[var(--canvas-inset)] px-2.5 py-0.5 font-medium text-[var(--ink-faint)]">
                        {doc.access_level === "PUBLIC"
                          ? "Public"
                          : doc.access_level === "STUDENT"
                            ? "Students"
                            : doc.access_level === "FACULTY"
                              ? "Faculty"
                              : "Admins only"}
                      </span>
                      <span
                        className={cn(
                          "rounded-full border px-2.5 py-0.5 font-semibold",
                          doc.status === "ACTIVE"
                            ? "border-[var(--success)] bg-[var(--success-faint)] text-[var(--success)]"
                            : doc.status === "FAILED"
                              ? "border-[var(--danger)] bg-[var(--danger-faint)] text-[var(--danger)]"
                              : "border-[var(--edge-strong)] bg-[var(--canvas-inset)] text-[var(--ink-faint)]",
                        )}
                      >
                        {doc.status === "ACTIVE"
                          ? "Active"
                          : doc.status.charAt(0) +
                            doc.status.slice(1).toLowerCase()}
                      </span>
                      <span className="text-[var(--ink-ghost)]">
                        v{doc.version}
                      </span>
                    </div>
                  </li>
                ))}
              </ul>
            </section>
          </>
        )}
      </main>
    </div>
  );
}

export default function AdminPage() {
  return (
    <RequireAuth>
      <AdminShell />
    </RequireAuth>
  );
}