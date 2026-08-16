"use client";

import { useEffect, useState, useCallback, useMemo } from "react";
import { useRouter } from "next/navigation";
import { Shield, Users, FileText, MessageSquareText, ThumbsUp, RefreshCw, Loader2, AlertCircle, Search } from "lucide-react";

import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ConfirmDialog } from "@/components/common/confirm-dialog";
import { useAuth } from "@/lib/auth";
import { useToast } from "@/components/common/toast";
import { listAdminUsers, listAdminDocuments, getAdminStats, updateUserRole, type AdminUser, type AdminDocument, type AdminStats, type Role } from "@/lib/admin";
import { formatDate } from "@/lib/documents";
import { ApiError } from "@/lib/api";

type AdminTab = "OVERVIEW" | "USERS" | "DOCUMENTS";

export default function AdminPage() {
  const { user: currentUser } = useAuth();
  const router = useRouter();
  const { toast } = useToast();

  const [activeTab, setActiveTab] = useState<AdminTab>("OVERVIEW");
  const [stats, setStats] = useState<AdminStats | null>(null);
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [documents, setDocuments] = useState<AdminDocument[]>([]);
  
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState("");

  const [roleChangeUser, setRoleChangeUser] = useState<AdminUser | null>(null);
  const [targetRole, setTargetRole] = useState<Role>("STUDENT");
  const [changingId, setChangingId] = useState<string | null>(null);

  // Authorization check
  useEffect(() => {
    if (currentUser && currentUser.role !== "ADMIN") {
      toast("Admin permissions required.", "error");
      router.replace("/dashboard");
    }
  }, [currentUser, router, toast]);

  const loadAdminData = useCallback(async (silent = false) => {
    if (!silent) setLoading(true);
    setError(null);
    try {
      const [statsData, usersData, docsData] = await Promise.all([
        getAdminStats(),
        listAdminUsers(),
        listAdminDocuments(),
      ]);
      setStats(statsData);
      setUsers(usersData);
      setDocuments(docsData);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Unable to load administrative controls.");
      toast("Failed to load admin logs.", "error");
    } finally {
      setLoading(false);
    }
  }, [toast]);

  useEffect(() => {
    if (currentUser?.role === "ADMIN") {
      void loadAdminData();
    }
  }, [currentUser, loadAdminData]);

  // Initiate role change confirmation modal
  const handleRoleSelectChange = (user: AdminUser, newRole: Role) => {
    setRoleChangeUser(user);
    setTargetRole(newRole);
  };

  const handleConfirmRoleChange = async () => {
    if (!roleChangeUser) return;
    setChangingId(roleChangeUser.id);
    try {
      const updated = await updateUserRole(roleChangeUser.id, targetRole);
      setUsers((prev) =>
        prev.map((u) => (u.id === roleChangeUser.id ? { ...u, role: updated.role } : u))
      );
      toast(`Updated ${roleChangeUser.name}'s role to ${targetRole}.`, "success");
      // Reload stats for user counts alignment
      void loadAdminData(true);
    } catch (err) {
      const message = err instanceof ApiError ? err.message : "Failed to change user role.";
      toast(message, "error");
    } finally {
      setChangingId(null);
      setRoleChangeUser(null);
    }
  };

  // Filter lists based on tab + search query
  const filteredUsers = useMemo(() => {
    if (activeTab !== "USERS") return [];
    return users.filter(
      (u) =>
        u.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
        u.email.toLowerCase().includes(searchQuery.toLowerCase())
    );
  }, [users, searchQuery, activeTab]);

  const filteredDocs = useMemo(() => {
    if (activeTab !== "DOCUMENTS") return [];
    return documents.filter(
      (d) =>
        d.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
        (d.owner_name && d.owner_name.toLowerCase().includes(searchQuery.toLowerCase()))
    );
  }, [documents, searchQuery, activeTab]);

  if (loading) {
    return (
      <div className="mx-auto max-w-5xl px-6 py-10 space-y-8">
        <div className="flex justify-between items-center">
          <div className="h-8 w-24 skeleton" />
          <div className="h-10 w-20 skeleton" />
        </div>
        <div className="h-12 w-96 skeleton" />
        <div className="grid gap-6 md:grid-cols-3">
          {[1, 2, 3].map((n) => (
            <div key={n} className="h-32 skeleton" />
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-5xl px-4 py-8 sm:px-6 space-y-6 animate-page-in">
      {/* Header Title */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl tracking-tight text-[var(--ink)]" style={{ fontFamily: "var(--font-display)" }}>
            Admin Console
          </h1>
          <p className="text-xs text-[var(--ink-faint)]">
            Manage user authorization, documents metadata, system audit, and diagnostics logs.
          </p>
        </div>
        <Button variant="outline" size="sm" onClick={() => void loadAdminData(true)}>
          <RefreshCw className="h-3.5 w-3.5" aria-hidden />
        </Button>
      </div>

      {error && <Alert variant="error">{error}</Alert>}

      {/* Tab selection row */}
      <div className="border-b border-[var(--edge)] flex items-center justify-between">
        <div className="flex gap-4">
          {(["OVERVIEW", "USERS", "DOCUMENTS"] as AdminTab[]).map((tab) => (
            <button
              key={tab}
              type="button"
              onClick={() => {
                setActiveTab(tab);
                setSearchQuery("");
              }}
              className={`pb-3 text-xs font-bold uppercase tracking-wider relative transition-all ${
                activeTab === tab
                  ? "text-[var(--primary)] font-semibold"
                  : "text-[var(--ink-faint)] hover:text-[var(--ink)]"
              }`}
            >
              {tab.toLowerCase()}
              {activeTab === tab && (
                <span className="absolute bottom-0 left-0 right-0 h-[2px] bg-[var(--primary)] rounded-full animate-page-in" />
              )}
            </button>
          ))}
        </div>

        {/* Local Search input */}
        {activeTab !== "OVERVIEW" && (
          <div className="relative w-48 sm:w-64 mb-2">
            <Search className="absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-[var(--ink-ghost)]" aria-hidden />
            <Input
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder={activeTab === "USERS" ? "Search users…" : "Search documents…"}
              className="pl-8 h-8 text-xs"
            />
          </div>
        )}
      </div>

      {/* OVERVIEW TAB CONTENT */}
      {activeTab === "OVERVIEW" && stats && (
        <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
          {/* Total users */}
          <div className="rounded-[var(--radius-lg)] border border-[var(--edge)] bg-[var(--canvas-raised)] p-5 shadow-[var(--shadow-sm)] space-y-2">
            <div className="flex items-center gap-2 text-[var(--ink-faint)]">
              <Users className="h-4 w-4" aria-hidden />
              <span className="text-[10px] font-bold uppercase tracking-wider">Total Users</span>
            </div>
            <p className="text-3xl text-[var(--ink)]" style={{ fontFamily: "var(--font-display)" }}>
              {stats.users}
            </p>
          </div>

          {/* Active documents */}
          <div className="rounded-[var(--radius-lg)] border border-[var(--edge)] bg-[var(--canvas-raised)] p-5 shadow-[var(--shadow-sm)] space-y-2">
            <div className="flex items-center gap-2 text-[var(--ink-faint)]">
              <FileText className="h-4 w-4" aria-hidden />
              <span className="text-[10px] font-bold uppercase tracking-wider">Active Documents</span>
            </div>
            <p className="text-3xl text-[var(--ink)]" style={{ fontFamily: "var(--font-display)" }}>
              {stats.active_documents}
              <span className="text-xs font-normal text-[var(--ink-faint)] ml-1">
                / {stats.documents} total
              </span>
            </p>
          </div>

          {/* Failed documents - Warning variant */}
          <div className={`rounded-[var(--radius-lg)] border p-5 shadow-[var(--shadow-sm)] space-y-2 ${
            stats.failed_documents > 0
              ? "border-[var(--danger)]/30 bg-[var(--danger-faint)]"
              : "border-[var(--edge)] bg-[var(--canvas-raised)]"
          }`}>
            <div className={`flex items-center gap-2 ${stats.failed_documents > 0 ? "text-[var(--danger)]" : "text-[var(--ink-faint)]"}`}>
              <AlertCircle className="h-4 w-4" aria-hidden />
              <span className="text-[10px] font-bold uppercase tracking-wider">Failed Documents</span>
            </div>
            <p className={`text-3xl ${stats.failed_documents > 0 ? "text-[var(--danger)] font-semibold" : "text-[var(--ink)]"}`} style={{ fontFamily: "var(--font-display)" }}>
              {stats.failed_documents}
            </p>
          </div>

          {/* Conversations count */}
          <div className="rounded-[var(--radius-lg)] border border-[var(--edge)] bg-[var(--canvas-raised)] p-5 shadow-[var(--shadow-sm)] space-y-2">
            <div className="flex items-center gap-2 text-[var(--ink-faint)]">
              <MessageSquareText className="h-4 w-4" aria-hidden />
              <span className="text-[10px] font-bold uppercase tracking-wider">Total Conversations</span>
            </div>
            <p className="text-3xl text-[var(--ink)]" style={{ fontFamily: "var(--font-display)" }}>
              {stats.conversations}
            </p>
          </div>

          {/* Feedback items count */}
          <div className="rounded-[var(--radius-lg)] border border-[var(--edge)] bg-[var(--canvas-raised)] p-5 shadow-[var(--shadow-sm)] space-y-2">
            <div className="flex items-center gap-2 text-[var(--ink-faint)]">
              <ThumbsUp className="h-4 w-4" aria-hidden />
              <span className="text-[10px] font-bold uppercase tracking-wider">Feedback Submissions</span>
            </div>
            <p className="text-3xl text-[var(--ink)]" style={{ fontFamily: "var(--font-display)" }}>
              {stats.feedback_entries}
            </p>
          </div>
        </div>
      )}

      {/* USERS TAB CONTENT */}
      {activeTab === "USERS" && (
        <div className="rounded-[var(--radius-lg)] border border-[var(--edge)] bg-[var(--canvas-raised)] overflow-hidden shadow-[var(--shadow-sm)]">
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse text-xs">
              <thead>
                <tr className="bg-[var(--canvas-inset)] border-b border-[var(--edge)] text-[var(--ink-faint)] font-bold uppercase tracking-wider">
                  <th className="px-4 py-3">User Info</th>
                  <th className="px-4 py-3">Registration Date</th>
                  <th className="px-4 py-3">Permission Role</th>
                  <th className="px-4 py-3 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[var(--edge)]">
                {filteredUsers.length === 0 ? (
                  <tr>
                    <td colSpan={4} className="px-4 py-8 text-center text-[var(--ink-ghost)]">
                      No matching user records.
                    </td>
                  </tr>
                ) : (
                  filteredUsers.map((u) => {
                    const isSelf = u.id === currentUser?.id;
                    const isChanging = changingId === u.id;
                    return (
                      <tr key={u.id} className="hover:bg-[var(--canvas-inset)]/30">
                        <td className="px-4 py-3">
                          <p className="font-semibold text-[var(--ink)]">
                            {u.name} {isSelf && <span className="text-[10px] font-normal text-[var(--ink-ghost)]">(you)</span>}
                          </p>
                          <p className="text-[10px] text-[var(--ink-faint)]">{u.email}</p>
                        </td>
                        <td className="px-4 py-3 text-[var(--ink-muted)]">
                          {formatDate(u.created_at)}
                        </td>
                        <td className="px-4 py-3">
                          <span className={`inline-flex items-center rounded-full border px-2 py-0.5 text-[9px] font-bold uppercase tracking-wider ${
                            u.role === "ADMIN"
                              ? "border-[var(--ink)] bg-[var(--canvas-inset)] text-[var(--ink)]"
                              : u.role === "FACULTY"
                              ? "border-[var(--primary)] bg-[var(--primary-faint)] text-[var(--primary)]"
                              : "border-[var(--info)] bg-[var(--info-faint)] text-[var(--info)]"
                          }`}>
                            {u.role}
                          </span>
                        </td>
                        <td className="px-4 py-3 text-right">
                          <div className="inline-flex items-center gap-2">
                            {isChanging ? (
                              <Loader2 className="h-4 w-4 text-[var(--primary)] animate-spin" />
                            ) : (
                              <select
                                value={u.role}
                                onChange={(e) => handleRoleSelectChange(u, e.target.value as Role)}
                                disabled={isSelf}
                                className="rounded border border-[var(--edge-strong)] bg-[var(--canvas-raised)] px-2 py-1 text-xs text-[var(--ink-muted)] hover:border-[var(--primary)] focus:outline-none transition-colors"
                              >
                                <option value="STUDENT">Student</option>
                                <option value="FACULTY">Faculty</option>
                                <option value="ADMIN">Admin</option>
                              </select>
                            )}
                          </div>
                        </td>
                      </tr>
                    );
                  })
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* DOCUMENTS TAB CONTENT */}
      {activeTab === "DOCUMENTS" && (
        <div className="rounded-[var(--radius-lg)] border border-[var(--edge)] bg-[var(--canvas-raised)] overflow-hidden shadow-[var(--shadow-sm)]">
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse text-xs">
              <thead>
                <tr className="bg-[var(--canvas-inset)] border-b border-[var(--edge)] text-[var(--ink-faint)] font-bold uppercase tracking-wider">
                  <th className="px-4 py-3">Document Details</th>
                  <th className="px-4 py-3">Uploader</th>
                  <th className="px-4 py-3">Access Level</th>
                  <th className="px-4 py-3">Status</th>
                  <th className="px-4 py-3 text-right">Audit</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[var(--edge)]">
                {filteredDocs.length === 0 ? (
                  <tr>
                    <td colSpan={5} className="px-4 py-8 text-center text-[var(--ink-ghost)]">
                      No matching documents logged.
                    </td>
                  </tr>
                ) : (
                  filteredDocs.map((doc) => (
                    <tr key={doc.id} className="hover:bg-[var(--canvas-inset)]/30">
                      <td className="px-4 py-3">
                        <p className="font-semibold text-[var(--ink)]">{doc.title}</p>
                        <p className="text-[9px] text-[var(--ink-ghost)]">Uploaded {formatDate(doc.created_at)}</p>
                      </td>
                      <td className="px-4 py-3 text-[var(--ink-muted)]">
                        {doc.owner_name ?? "System"}
                      </td>
                      <td className="px-4 py-3">
                        <span className="rounded border border-[var(--edge)] bg-[var(--canvas-inset)] px-2 py-0.5 font-medium text-[var(--ink-faint)] uppercase text-[9px] tracking-wider">
                          {doc.access_level}
                        </span>
                      </td>
                      <td className="px-4 py-3">
                        <span className={`inline-flex items-center rounded-full border px-2 py-0.5 text-[9px] font-bold uppercase tracking-wider ${
                          doc.status === "ACTIVE"
                            ? "border-[var(--success)] bg-[var(--success-faint)] text-[var(--success)]"
                            : doc.status === "FAILED"
                            ? "border-[var(--danger)] bg-[var(--danger-faint)] text-[var(--danger)]"
                            : "border-[var(--edge-strong)] bg-[var(--canvas-inset)] text-[var(--ink-faint)]"
                        }`}>
                          {doc.status}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-right text-[var(--ink-ghost)]">
                        v{doc.version} · {doc.page_count ?? "—"} pgs · {doc.chunk_count ?? "0"} chunks
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Role Change Confirmation Modal */}
      <ConfirmDialog
        open={!!roleChangeUser}
        title="Change user permissions?"
        description={`Confirm updating ${roleChangeUser?.name}'s access permissions to ${targetRole}. Last remaining ADMIN user demotions will be blocked by the server.`}
        confirmLabel="Update Role"
        variant="default"
        onConfirm={handleConfirmRoleChange}
        onCancel={() => setRoleChangeUser(null)}
      />
    </div>
  );
}
export const dynamic = "force-dynamic";
