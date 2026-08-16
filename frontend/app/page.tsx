"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { ArrowRight, BookOpen, MessageSquare, Shield, Search, Database, RefreshCw, FileText } from "lucide-react";

import { DemoChat } from "@/components/demo-chat";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/lib/auth";
import { getDemoInfo, type DemoInfo } from "@/lib/demo";

export default function Home() {
  const { user, status } = useAuth();
  const [demo, setDemo] = useState<DemoInfo | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    getDemoInfo()
      .then((info) => {
        if (!cancelled) {
          setDemo(info);
          setLoading(false);
        }
      })
      .catch(() => {
        if (!cancelled) {
          setDemo(null);
          setLoading(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-[var(--canvas)]">
        <div className="flex flex-col items-center gap-3">
          <div
            className="h-8 w-8 rounded-full border-2 border-[var(--edge-strong)] border-t-[var(--primary)]"
            style={{ animation: "spin 0.7s linear infinite" }}
            aria-label="Loading"
          />
          <span className="text-sm text-[var(--ink-faint)]">Loading DocMind…</span>
        </div>
      </div>
    );
  }

  // Render Public Demo Chat mode if active
  if (demo?.demo_mode) {
    return (
      <main className="flex min-h-screen flex-col bg-[var(--canvas)] text-[var(--ink)]">
        <header className="border-b border-[var(--edge)] bg-[var(--canvas-raised)]">
          <nav className="mx-auto flex max-w-5xl items-center justify-between px-6 py-4">
            <div className="flex items-center gap-3">
              <span className="flex h-9 w-9 items-center justify-center rounded-[var(--radius-sm)] bg-[var(--ink)] text-[var(--canvas)] font-bold text-sm">
                D
              </span>
              <span className="text-xl tracking-tight text-[var(--ink)]" style={{ fontFamily: "var(--font-display)" }}>
                DocMind
              </span>
            </div>
            <div className="flex items-center gap-2">
              <span className="rounded-full bg-[var(--primary-faint)] px-2.5 py-0.5 text-xs font-bold uppercase tracking-wider text-[var(--primary)]">
                Demo active
              </span>
            </div>
          </nav>
        </header>
        <div className="flex-1 flex flex-col justify-center">
          <DemoChat info={demo} />
        </div>
      </main>
    );
  }

  // Render Landing Page
  return (
    <main className="flex min-h-screen flex-col bg-[var(--canvas)] text-[var(--ink)]">
      {/* Header */}
      <header className="border-b border-[var(--edge)] bg-[var(--canvas-raised)]">
        <nav className="mx-auto flex max-w-5xl items-center justify-between px-6 py-4">
          <div className="flex items-center gap-3">
            <span className="flex h-9 w-9 items-center justify-center rounded-[var(--radius-sm)] bg-[var(--ink)] text-[var(--canvas)] font-bold text-sm">
              D
            </span>
            <span className="text-xl tracking-tight" style={{ fontFamily: "var(--font-display)" }}>
              DocMind
            </span>
          </div>

          <div className="flex items-center gap-3">
            {status === "authenticated" && user ? (
              <div className="flex items-center gap-3">
                <span className="hidden text-sm text-[var(--ink-faint)] sm:inline">
                  {user.name}
                </span>
                <Link href="/dashboard">
                  <Button size="sm" variant="primary">Dashboard</Button>
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
                  <Button variant="primary" size="sm">
                    Get started
                  </Button>
                </Link>
              </div>
            )}
          </div>
        </nav>
      </header>

      {/* Hero */}
      <section className="mx-auto max-w-4xl px-6 py-20 text-center animate-page-in">
        <div className="space-y-6">
          <span className="inline-flex items-center gap-1.5 rounded-full border border-[var(--primary-muted)] bg-[var(--primary-faint)] px-3 py-1 text-xs font-semibold text-[var(--primary)]">
            Document Intelligence Platform
          </span>
          <h1 className="text-5xl tracking-tight text-[var(--ink)] sm:text-6xl" style={{ fontFamily: "var(--font-display)" }}>
            Understand your documents.<br />
            Ask better questions.
          </h1>
          <p className="mx-auto max-w-xl text-lg text-[var(--ink-muted)] leading-relaxed">
            DocMind parses complex university regulations, guidelines, and ordinance documents into searchable, grounded knowledge. Retrieve answers backed directly by sources.
          </p>
          <div className="flex justify-center gap-4 pt-4">
            <Link href="/register">
              <Button variant="primary" size="lg">
                Create Account
                <ArrowRight className="h-4 w-4 ml-1.5" />
              </Button>
            </Link>
            <Link href="/login">
              <Button variant="outline" size="lg">
                Sign in
              </Button>
            </Link>
          </div>
        </div>
      </section>

      {/* Product Preview */}
      <section className="mx-auto max-w-4xl px-6 pb-20">
        <div className="rounded-[var(--radius-lg)] border border-[var(--edge-strong)] bg-[var(--canvas-raised)] p-6 shadow-[var(--shadow-lg)]">
          <div className="border-b border-[var(--edge)] pb-4 mb-4 flex items-center justify-between">
            <div className="flex items-center gap-2.5">
              <span className="h-3.5 w-3.5 rounded-full bg-[var(--danger)]" />
              <span className="h-3.5 w-3.5 rounded-full bg-[var(--warning)]" />
              <span className="h-3.5 w-3.5 rounded-full bg-[var(--success)]" />
            </div>
            <span className="text-[10px] font-bold uppercase tracking-wider text-[var(--ink-ghost)]">
              Interactive Preview
            </span>
          </div>

          <div className="space-y-4">
            {/* User message */}
            <div className="rounded-[var(--radius-md)] border border-[var(--primary-muted)] bg-[var(--primary-faint)]/40 p-4 ml-12">
              <span className="text-[9px] font-bold uppercase tracking-wider text-[var(--ink-faint)]">
                You
              </span>
              <p className="mt-1 text-sm text-[var(--ink)] leading-relaxed">
                What is the minimum attendance requirement for examinations?
              </p>
            </div>

            {/* Assistant message */}
            <div className="rounded-[var(--radius-md)] border border-[var(--edge)] bg-[var(--canvas)] p-4 mr-12 border-l-4 border-l-[var(--ink)]">
              <span className="text-[9px] font-bold uppercase tracking-wider text-[var(--ink-faint)]">
                DocMind
              </span>
              <p className="mt-1 text-sm text-[var(--ink)] leading-relaxed">
                The minimum attendance requirement for admission to examinations is 75% of the total lectures delivered in each course. <button type="button" className="mx-0.5 inline-flex h-4 min-w-4 items-center justify-center rounded bg-[var(--primary-faint)] px-1 text-[9px] font-bold text-[var(--primary)]">1</button>
              </p>
              
              {/* Sources */}
              <div className="mt-4 border-t border-[var(--edge-strong)] pt-3">
                <span className="text-[9px] font-bold uppercase tracking-wider text-[var(--ink-faint)] block mb-1.5">
                  Sources
                </span>
                <div className="inline-flex items-center gap-1.5 rounded-full border border-[var(--edge)] bg-[var(--canvas-raised)] px-3 py-1 text-xs text-[var(--ink-muted)]">
                  <span className="flex h-3.5 w-3.5 items-center justify-center rounded-full bg-[var(--ink-ghost)] text-[9px] font-bold text-[var(--ink-muted)]">
                    1
                  </span>
                  <span className="font-semibold text-[var(--ink)]">Examination Ordinance</span>
                  <span className="text-[var(--ink-faint)]">· Page 14</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Features */}
      <section className="bg-[var(--canvas-inset)] border-t border-b border-[var(--edge)] py-20">
        <div className="mx-auto max-w-5xl px-6">
          <div className="text-center space-y-3 mb-16">
            <h2 className="text-3xl font-semibold text-[var(--ink)]" style={{ fontFamily: "var(--font-display)" }}>
              Sophisticated RAG Pipelines
            </h2>
            <p className="text-sm text-[var(--ink-muted)] max-w-md mx-auto">
              Behind the simple interface lies a complete information retrieval and generation engine.
            </p>
          </div>

          <div className="grid gap-8 md:grid-cols-3">
            <div className="bg-[var(--canvas-raised)] border border-[var(--edge)] rounded-[var(--radius-lg)] p-6 space-y-4">
              <span className="flex h-10 w-10 items-center justify-center rounded-[var(--radius-md)] bg-[var(--primary-faint)] text-[var(--primary)]">
                <RefreshCw className="h-5 w-5" aria-hidden />
              </span>
              <h3 className="text-lg font-semibold text-[var(--ink)]" style={{ fontFamily: "var(--font-display)" }}>
                Hybrid Retrieval
              </h3>
              <p className="text-xs text-[var(--ink-muted)] leading-relaxed">
                Combines semantic embedding dense search (BGE embeddings) with traditional keyword match (BM25) for absolute coverage.
              </p>
            </div>

            <div className="bg-[var(--canvas-raised)] border border-[var(--edge)] rounded-[var(--radius-lg)] p-6 space-y-4">
              <span className="flex h-10 w-10 items-center justify-center rounded-[var(--radius-md)] bg-[var(--primary-faint)] text-[var(--primary)]">
                <Search className="h-5 w-5" aria-hidden />
              </span>
              <h3 className="text-lg font-semibold text-[var(--ink)]" style={{ fontFamily: "var(--font-display)" }}>
                Cross-Encoder Reranking
              </h3>
              <p className="text-xs text-[var(--ink-muted)] leading-relaxed">
                Calculates precise matching relevance values via high-quality reranking layers to surface only verified evidence.
              </p>
            </div>

            <div className="bg-[var(--canvas-raised)] border border-[var(--edge)] rounded-[var(--radius-lg)] p-6 space-y-4">
              <span className="flex h-10 w-10 items-center justify-center rounded-[var(--radius-md)] bg-[var(--primary-faint)] text-[var(--primary)]">
                <Shield className="h-5 w-5" aria-hidden />
              </span>
              <h3 className="text-lg font-semibold text-[var(--ink)]" style={{ fontFamily: "var(--font-display)" }}>
                Access Permissions
              </h3>
              <p className="text-xs text-[var(--ink-muted)] leading-relaxed">
                Features role-based controls (Student, Faculty, Admin) to ensure users can only search documents they have access to.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* Architecture pipeline */}
      <section className="mx-auto max-w-4xl px-6 py-20 text-center">
        <h2 className="text-3xl font-semibold text-[var(--ink)] mb-12" style={{ fontFamily: "var(--font-display)" }}>
          Technical Architecture Pipeline
        </h2>
        <div className="flex flex-col md:flex-row items-center justify-between gap-4 md:gap-2">
          {["Documents", "Ingestion", "Embeddings", "Hybrid Match", "Reranker", "Grounded Answer"].map((step, idx) => (
            <div key={idx} className="flex items-center w-full md:w-auto">
              <div className="flex-1 md:flex-initial rounded-[var(--radius-md)] border border-[var(--edge-strong)] bg-[var(--canvas-raised)] px-4 py-2.5 text-xs font-semibold text-[var(--ink)]">
                {step}
              </div>
              {idx < 5 && (
                <span className="hidden md:block text-[var(--ink-ghost)] px-2 font-bold">→</span>
              )}
            </div>
          ))}
        </div>
      </section>

      {/* CTA */}
      <section className="bg-[var(--ink)] text-[var(--canvas-raised)] text-center py-20 border-t border-[var(--edge)]">
        <div className="space-y-6 max-w-lg mx-auto px-6">
          <h2 className="text-3xl font-semibold tracking-tight" style={{ fontFamily: "var(--font-display)" }}>
            Get started with DocMind
          </h2>
          <p className="text-xs text-[var(--ink-ghost)] leading-relaxed">
            Create an account to start uploading university ordinances, index them, and ask natural language questions.
          </p>
          <div className="pt-2">
            <Link href="/register">
              <Button variant="accent" size="lg" className="bg-[var(--primary)] text-white hover:bg-[var(--primary-hover)]">
                Get Started Now
              </Button>
            </Link>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t border-[var(--edge)] bg-[var(--canvas-raised)] py-8 text-center text-xs text-[var(--ink-ghost)]">
        &copy; {new Date().getFullYear()} DocMind University Knowledge Platform. Built for grounded verification.
      </footer>
    </main>
  );
}
