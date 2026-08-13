"use client";

import { useRouter } from "next/navigation";
import { BookOpen, LayoutDashboard, ShieldCheck } from "lucide-react";

import { RequireAuth } from "@/components/require-auth";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/lib/auth";

function DashboardShell() {
  const { user, status, logout } = useAuth();
  const router = useRouter();

  function handleLogout() {
    logout();
    router.push("/");
  }

  return (
    <div className="min-h-screen bg-zinc-50 text-zinc-900">
      <header className="border-b border-zinc-200 bg-white">
        <div className="mx-auto flex max-w-4xl items-center justify-between px-6 py-4">
          <div className="flex items-center gap-2 font-semibold">
            <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-indigo-600 text-white">
              <BookOpen className="h-4 w-4" aria-hidden />
            </span>
            CampusRAG
          </div>
          <div className="flex items-center gap-3">
            <span className="hidden text-sm text-zinc-600 sm:inline">
              {user?.email}
            </span>
            <Button variant="outline" size="sm" onClick={handleLogout}>
              Logout
            </Button>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-4xl space-y-6 px-6 py-10">
        <section>
          <h1 className="text-3xl font-semibold tracking-tight">
            Welcome, {user?.name}
          </h1>
          <p className="mt-1 text-zinc-600">
            {user?.role === "ADMIN"
              ? "Administrator account"
              : user?.role === "FACULTY"
                ? "Faculty account"
                : "Student account"}
          </p>
        </section>

        <section className="grid gap-4 sm:grid-cols-2">
          <div className="rounded-xl border border-zinc-200 bg-white p-5 shadow-sm">
            <div className="flex items-center gap-2 text-zinc-500">
              <ShieldCheck className="h-4 w-4" aria-hidden />
              <h2 className="text-sm font-medium uppercase tracking-wide">
                Authentication status
              </h2>
            </div>
            <p className="mt-3 text-sm text-zinc-700">
              Status:{" "}
              <span className="font-medium text-emerald-600">
                {status === "authenticated" ? "authenticated" : status}
              </span>
            </p>
            <p className="mt-1 text-sm text-zinc-500">
              Role:{" "}
              <span className="font-medium text-zinc-700">{user?.role}</span>
            </p>
          </div>

          <div className="flex flex-col justify-between rounded-xl border border-dashed border-zinc-300 bg-white p-5 shadow-sm">
            <div className="flex items-center gap-2 text-zinc-500">
              <LayoutDashboard className="h-4 w-4" aria-hidden />
              <h2 className="text-sm font-medium uppercase tracking-wide">
                Dashboard
              </h2>
            </div>
            <p className="mt-3 text-sm text-zinc-600">
              Document management and the RAG chat arrive in later phases.
            </p>
          </div>
        </section>
      </main>
    </div>
  );
}

export default function DashboardPage() {
  return (
    <RequireAuth>
      <DashboardShell />
    </RequireAuth>
  );
}
