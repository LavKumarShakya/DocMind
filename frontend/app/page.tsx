"use client";

import { useEffect, useState } from "react";
import { BookOpen, Database, Loader2, Server, TriangleAlert } from "lucide-react";
import { apiGet } from "@/lib/api";
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

export default function Home() {
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
    <main className="flex min-h-screen items-center justify-center bg-zinc-50 text-zinc-900">
      <section className="w-full max-w-lg space-y-6 px-6 py-12 text-center">
        <div className="flex items-center justify-center gap-3">
          <span className="flex h-12 w-12 items-center justify-center rounded-xl bg-indigo-600 text-white shadow-sm">
            <BookOpen className="h-6 w-6" aria-hidden />
          </span>
          <h1 className="text-4xl font-semibold tracking-tight">CampusRAG</h1>
        </div>
        <p className="text-zinc-600">
          University knowledge retrieval and question-answering platform.
        </p>

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
      </section>
    </main>
  );
}
