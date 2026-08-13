"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { BookOpen, Database, Loader2, Server, TriangleAlert } from "lucide-react";

import { Button } from "@/components/ui/button";
import { apiGet } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { cn } from "@/lib/utils";

type Health = {
  status: string;
  version: string;
  environment: string;
  database: string;
};

type StatusState =
  | { kind: "loading" }
  | { kind: "success"; health: Health }
  | { kind: "error"; message: string };

function HealthCard() {
  const [state, setState] = useState<StatusState>({ kind: "loading" });

  useEffect(() => {
    let cancelled = false;
    apiGet<Health>("/api/health")
      .then((health) => {
        if (!cancelled) setState({ kind: "success", health });
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setState({
            kind: "error",
            message: err instanceof Error ? err.message : "Unknown error",
          });
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <div className="rounded-xl border border-zinc-200 bg-white p-6 text-left shadow-sm">
      <h2 className="text-sm font-medium uppercase tracking-wide text-zinc-400">
        System status
      </h2>

      {state.kind === "loading" && (
        <div className="mt-4 flex items-center gap-2 text-sm text-zinc-500">
          <Loader2 className="h-4 w-4 animate-spin" aria-hidden />
          Checking backend health…
        </div>
      )}

      {state.kind === "error" && (
        <div className="mt-4 flex items-start gap-2 rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">
          <TriangleAlert className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
          <span>
            Backend unreachable: {state.message}. Is the API running?
          </span>
        </div>
      )}

      {state.kind === "success" && (
        <dl className="mt-4 grid grid-cols-2 gap-y-3 text-sm">
          <div className="flex items-center gap-2">
            <Server className="h-4 w-4 text-zinc-400" aria-hidden />
            <dt className="text-zinc-500">API status</dt>
          </div>
          <dd
            className={cn(
              "text-right font-medium",
              state.health.status === "ok" ? "text-emerald-600" : "text-amber-600",
            )}
          >
            {state.health.status}
          </dd>

          <div className="flex items-center gap-2">
            <Database className="h-4 w-4 text-zinc-400" aria-hidden />
            <dt className="text-zinc-500">Database</dt>
          </div>
          <dd className="text-right font-medium">{state.health.database}</dd>

          <dt className="text-zinc-500">API version</dt>
          <dd className="text-right font-medium">{state.health.version}</dd>

          <dt className="text-zinc-500">Environment</dt>
          <dd className="text-right font-medium">{state.health.environment}</dd>
        </dl>
      )}
    </div>
  );
}

export default function Home() {
  const { user, status } = useAuth();

  return (
    <main className="flex min-h-screen flex-col bg-zinc-50 text-zinc-900">
      <header className="border-b border-zinc-200 bg-white/80">
        <nav className="mx-auto flex max-w-4xl items-center justify-between px-6 py-4">
          <div className="flex items-center gap-2 font-semibold">
            <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-indigo-600 text-white">
              <BookOpen className="h-4 w-4" aria-hidden />
            </span>
            CampusRAG
          </div>

          {status === "loading" ? null : user ? (
            <div className="flex items-center gap-3">
              <span className="hidden text-sm text-zinc-600 sm:inline">
                {user.name}
              </span>
              <Link href="/dashboard">
                <Button size="sm">Dashboard</Button>
              </Link>
            </div>
          ) : (
            <div className="flex items-center gap-2">
              <Link href="/login">
                <Button variant="ghost" size="sm">
                  Sign in
                </Button>
              </Link>
              <Link href="/register">
                <Button size="sm">Create account</Button>
              </Link>
            </div>
          )}
        </nav>
      </header>

      <section className="flex flex-1 items-center justify-center px-6 py-12">
        <div className="w-full max-w-lg space-y-6 text-center">
          <h1 className="text-4xl font-semibold tracking-tight">CampusRAG</h1>
          <p className="text-zinc-600">
            University knowledge retrieval and question-answering platform.
          </p>
          <HealthCard />
        </div>
      </section>
    </main>
  );
}
