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

const roleStyles: Record<Role, string> = {
  STUDENT: "bg-blue-50 text-blue-700 border-blue-200",
  FACULTY: "bg-amber-50 text-amber-700 border-amber-200",
  ADMIN: "bg-indigo-50 text-indigo-700 border-indigo-200",
};

function RoleBadge({ role }: { role: Role }) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-medium",
        roleStyles[role],
      )}
    >
      {role.charAt(0) + role.slice(1).toLowerCase()}
    </span>
  );
}

function StatCard({
  icon,
  label,
  value,
}: {
  icon: React.ReactNode;
  label: string;
  value: number;
}) {
  return (
    <div className="rounded-xl border border-zinc-200 bg-white p-5 shadow-sm">
      <div className="flex items-center gap-2 text-zinc-500">
        {icon}
        <span className="text-xs font-medium uppercase tracking-wide">
          {label}
        </span>
      </div>
      <p className="mt-2 text-3xl font-semibold text-zinc-900">{value}</p>
    </div>
  );
}

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
    <div className="min-h-screen bg-zinc-50 text-zinc-900">
      <SiteHeader />

      <main className="mx-auto max-w-6xl space-y-8 px-6 py-10">
        <section className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-semibold tracking-tight">Admin</h1>
            <p className="mt-1 text-zinc-600">
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

        {loading && (
          <div className="flex items-center gap-2 text-sm text-zinc-500">
            <Loader2 className="h-4 w-4 animate-spin" aria-hidden />
            Loading admin data…
          </div>
        )}

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
            <div className="rounded-xl border border-red-200 bg-red-50 p-5">
              <div className="flex items-center gap-2 text-red-600">
                <FileText className="h-4 w-4" aria-hidden />
                <span className="text-xs font-medium uppercase tracking-wide">
                  Failed documents
                </span>
              </div>
              <p className="mt-2 text-3xl font-semibold text-red-700">
                {stats.failed_documents}
              </p>
            </div>
          </section>
        )}

        {!loading && (
          <>
            <section>
              <div className="flex items-center gap-2">
                <Users className="h-4 w-4 text-zinc-500" aria-hidden />
                <h2 className="text-sm font-medium uppercase tracking-wide text-zinc-500">
                  Users
                </h2>
                <span className="rounded-full bg-zinc-100 px-2 py-0.5 text-xs text-zinc-600">
                  {users.length}
                </span>
              </div>
              <ul className="mt-4 space-y-2">
                {users.map((adminUser) => (
                  <li
                    key={adminUser.id}
                    className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-zinc-200 bg-white p-4 shadow-sm"
                  >
                    <div className="min-w-0">
                      <p className="font-medium text-zinc-900">
                        {adminUser.name}
                        {adminUser.id === user?.id && (
                          <span className="ml-2 text-xs font-normal text-zinc-400">
                            (you)
                          </span>
                        )}
                      </p>
                      <p className="text-sm text-zinc-500">{adminUser.email}</p>
                    </div>
                    <div className="flex items-center gap-3">
                      <RoleBadge role={adminUser.role} />
                      <select
                        value={adminUser.role}
                        disabled={changingRole === adminUser.id}
                        onChange={(e) =>
                          handleRoleChange(adminUser.id, e.target.value as Role)
                        }
                        className="h-8 rounded-lg border border-zinc-300 bg-white px-2 text-xs text-zinc-700 focus:border-indigo-500 focus:outline-none"
                        aria-label={`Change role for ${adminUser.name}`}
                      >
                        <option value="STUDENT">Student</option>
                        <option value="FACULTY">Faculty</option>
                        <option value="ADMIN">Admin</option>
                      </select>
                      {changingRole === adminUser.id && (
                        <Loader2 className="h-4 w-4 animate-spin text-zinc-400" aria-hidden />
                      )}
                    </div>
                  </li>
                ))}
              </ul>
            </section>

            <section>
              <div className="flex items-center gap-2">
                <FileText className="h-4 w-4 text-zinc-500" aria-hidden />
                <h2 className="text-sm font-medium uppercase tracking-wide text-zinc-500">
                  Documents
                </h2>
                <span className="rounded-full bg-zinc-100 px-2 py-0.5 text-xs text-zinc-600">
                  {documents.length}
                </span>
              </div>
              <ul className="mt-4 space-y-2">
                {documents.map((doc) => (
                  <li
                    key={doc.id}
                    className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-zinc-200 bg-white p-4 shadow-sm"
                  >
                    <div className="min-w-0">
                      <p className="font-medium text-zinc-900">{doc.title}</p>
                      <p className="text-sm text-zinc-500">
                        Uploaded by {doc.owner_name ?? "Unknown"} ·{" "}
                        {formatDate(doc.created_at)}
                        {doc.page_count != null &&
                          ` · ${doc.page_count} page${doc.page_count === 1 ? "" : "s"}`}
                      </p>
                    </div>
                    <div className="flex shrink-0 items-center gap-2 text-xs">
                      <span className="rounded-full border border-zinc-200 bg-zinc-50 px-2 py-0.5 text-zinc-600">
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
                          "rounded-full border px-2 py-0.5 font-medium",
                          doc.status === "ACTIVE"
                            ? "border-emerald-200 bg-emerald-50 text-emerald-700"
                            : doc.status === "FAILED"
                              ? "border-red-200 bg-red-50 text-red-700"
                              : "border-zinc-200 bg-zinc-50 text-zinc-600",
                        )}
                      >
                        {doc.status === "ACTIVE"
                          ? "Active"
                          : doc.status.charAt(0) + doc.status.slice(1).toLowerCase()}
                      </span>
                      <span className="text-zinc-400">v{doc.version}</span>
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