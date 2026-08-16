"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Database, Loader2, Server, TriangleAlert } from "lucide-react";

import { DemoChat } from "@/components/demo-chat";
import { Button } from "@/components/ui/button";
import { apiGet } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { getDemoInfo, type DemoInfo } from "@/lib/demo";
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
    <div className="rounded-[var(--radius-md)] border border-[var(--edge)] bg-[var(--canvas-raised)] p-6 text-left shadow-[var(--shadow-md)]">
      <h2
        className="text-xs font-semibold uppercase tracking-[0.1em] text-[var(--ink-faint)]"
      >
        System status
      </h2>

      {state.kind === "loading" && (
        <div className="mt-4 flex items-center gap-2 text-sm text-[var(--ink-faint)]">
          <Loader2
            className="h-4 w-4 text-[var(--accent)]"
            style={{ animation: "spin 0.7s linear infinite" }}
            aria-hidden
          />
          Checking backend health…
        </div>
      )}

      {state.kind === "error" && (
        <div className="mt-4 flex items-start gap-2 rounded-[var(--radius-sm)] border-l-[3px] border-l-[var(--danger)] bg-[var(--danger-faint)] p-3 text-sm text-[var(--danger)]">
          <TriangleAlert className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
          <span>
            Backend unreachable: {state.message}. Is the API running?
          </span>
        </div>
      )}

      {state.kind === "success" && (
        <dl className="mt-4 grid grid-cols-2 gap-y-3 text-sm">
          <div className="flex items-center gap-2">
            <Server className="h-4 w-4 text-[var(--ink-ghost)]" aria-hidden />
            <dt className="text-[var(--ink-faint)]">API status</dt>
          </div>
          <dd
            className={cn(
              "text-right font-semibold",
              state.health.status === "ok"
                ? "text-[var(--success)]"
                : "text-[var(--accent)]",
            )}
          >
            {state.health.status}
          </dd>

          <div className="flex items-center gap-2">
            <Database className="h-4 w-4 text-[var(--ink-ghost)]" aria-hidden />
            <dt className="text-[var(--ink-faint)]">Database</dt>
          </div>
          <dd className="text-right font-semibold text-[var(--ink)]">
            {state.health.database}
          </dd>

          <dt className="text-[var(--ink-faint)]">API version</dt>
          <dd className="text-right font-semibold text-[var(--ink)]">
            {state.health.version}
          </dd>

          <dt className="text-[var(--ink-faint)]">Environment</dt>
          <dd className="text-right font-semibold text-[var(--ink)]">
            {state.health.environment}
          </dd>
        </dl>
      )}
    </div>
  );
}

export default function Home() {
  const { user, status } = useAuth();
  const [demo, setDemo] = useState<DemoInfo | null>(null);

  useEffect(() => {
    let cancelled = false;
    getDemoInfo()
      .then((info) => {
        if (!cancelled) setDemo(info);
      })
      .catch(() => {
        // Demo endpoints return 404 when DEMO_MODE is off (and a network error
        // when the backend is unreachable): keep the standard landing page.
        if (!cancelled) setDemo(null);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <main className="flex min-h-screen flex-col bg-[var(--canvas)] text-[var(--ink)]">
      {/* Header */}
      <header className="border-b border-[var(--edge)] bg-[var(--canvas-raised)]">
        <nav className="mx-auto flex max-w-4xl items-center justify-between px-6 py-5">
          <div className="flex items-center gap-3">
            <span className="flex h-9 w-9 items-center justify-center rounded-[var(--radius-sm)] bg-[var(--ink)] text-[var(--canvas)] font-bold text-sm">
              D
            </span>
            <span
              className="text-xl tracking-tight"
              style={{ fontFamily: "var(--font-display)" }}
            >
              DocMind
            </span>
          </div>

          {status === "loading" ? null : user ? (
            <div className="flex items-center gap-3">
              <span className="hidden text-sm text-[var(--ink-faint)] sm:inline">
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
                <Button variant="accent" size="sm">
                  Create account
                </Button>
              </Link>
            </div>
          )}
        </nav>
      </header>

{demo?.demo_mode ? (
        <DemoChat info={demo} />
      ) : (
        /* Hero */
        <section className="flex flex-1 items-center justify-center px-6 py-16 animate-page-in">
          <div className="w-full max-w-lg space-y-8 text-center">
            {/* Decorative accent bar */}
            <div className="mx-auto h-1 w-12 rounded-full bg-[var(--accent)]" />

            <h1
              className="text-5xl tracking-tight text-[var(--ink)] sm:text-6xl"
              style={{ fontFamily: "var(--font-display)" }}
            >
              DocMind
            </h1>

            <p className="mx-auto max-w-sm text-lg text-[var(--ink-muted)] leading-relaxed">
              University knowledge retrieval and question&#8209;answering
              platform, grounded in your documents.
            </p>

            <HealthCard />

            {/* CTA for unauthenticated */}
            {status === "unauthenticated" && (
              <div className="flex justify-center gap-3 pt-2">
                <Link href="/register">
                  <Button variant="accent" size="lg">
                    Get Started
                  </Button>
                </Link>
                <Link href="/login">
                  <Button variant="outline" size="lg">
                    Sign in
                  </Button>
                </Link>
              </div>
            )}
          </div>
        </section>
      )}
    </main>
  );
}
