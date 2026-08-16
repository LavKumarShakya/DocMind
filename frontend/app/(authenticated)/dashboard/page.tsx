"use client";

import { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { MessageSquareText, FileText, Send, Plus, Loader2, ArrowRight } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useAuth } from "@/lib/auth";
import { listConversations, type ConversationSummary } from "@/lib/conversations";
import { listDocuments, type CampusDocument } from "@/lib/documents";
import { useToast } from "@/components/common/toast";
import { useDemoMode } from "@/lib/use-demo-mode";

const QUICK_QUESTIONS = [
  "What is the minimum attendance requirement?",
  "What are the examination rules?",
  "Who is eligible for scholarship?",
];

export default function DashboardPage() {
  const { user } = useAuth();
  const router = useRouter();
  const { toast } = useToast();
  const { isDemo, loading: demoLoading } = useDemoMode();

  const [question, setQuestion] = useState("");
  const [conversations, setConversations] = useState<ConversationSummary[]>([]);
  const [documents, setDocuments] = useState<CampusDocument[]>([]);
  const [loading, setLoading] = useState(true);

  // Load conversations & documents
  const loadData = useCallback(async () => {
    try {
      const [convoList, docList] = await Promise.all([
        listConversations().catch(() => []),
        listDocuments().catch(() => []),
      ]);
      setConversations(convoList.slice(0, 3)); // show top 3 recent
      setDocuments(docList.slice(0, 5)); // show top 5 active
    } catch {
      toast("Unable to load dashboard details.", "error");
    } finally {
      setLoading(false);
    }
  }, [toast]);

  useEffect(() => {
    if (!demoLoading && !isDemo) {
      void loadData();
    }
  }, [isDemo, demoLoading, loadData]);

  const handleAsk = (e: React.FormEvent) => {
    e.preventDefault();
    if (!question.trim()) return;
    // Redirect to chat with the pre-filled question
    router.push(`/chat?q=${encodeURIComponent(question.trim())}`);
  };

  const handleQuickAsk = (qText: string) => {
    router.push(`/chat?q=${encodeURIComponent(qText)}`);
  };

  // If backend is in Demo Mode, authenticated routes are disabled
  if (!demoLoading && isDemo) {
    return (
      <div className="flex min-h-[60vh] flex-col items-center justify-center p-6 text-center">
        <h2 className="text-2xl text-[var(--ink)]" style={{ fontFamily: "var(--font-display)" }}>
          Public Demo Active
        </h2>
        <p className="mt-3 max-w-sm text-sm text-[var(--ink-muted)] leading-relaxed">
          The dashboard is disabled while public demo is live. Please use the showcase chat.
        </p>
        <Link href="/" className="mt-6">
          <Button variant="primary">Go to Public Demo</Button>
        </Link>
      </div>
    );
  }

  // Loading skeleton
  if (loading || demoLoading) {
    return (
      <div className="mx-auto max-w-5xl px-6 py-10 space-y-8">
        <div className="h-10 w-48 skeleton" />
        <div className="h-24 w-full skeleton" />
        <div className="grid gap-6 md:grid-cols-2">
          <div className="h-48 skeleton" />
          <div className="h-48 skeleton" />
        </div>
      </div>
    );
  }

  // Dynamic greeting based on current time
  const getGreeting = () => {
    const hrs = new Date().getHours();
    if (hrs < 12) return "Good morning";
    if (hrs < 17) return "Good afternoon";
    return "Good evening";
  };

  return (
    <div className="mx-auto max-w-5xl px-4 py-8 sm:px-6 space-y-10 animate-page-in">
      {/* Greetings Header */}
      <section className="space-y-1">
        <h1 className="text-4xl tracking-tight text-[var(--ink)]" style={{ fontFamily: "var(--font-display)" }}>
          {getGreeting()}, {user?.name}
        </h1>
        <p className="text-sm text-[var(--ink-faint)] font-medium">
          Ask natural-language questions grounded in your document repository.
        </p>
      </section>

      {/* Ask Question block */}
      <section className="rounded-[var(--radius-lg)] border border-[var(--edge)] bg-[var(--canvas-raised)] p-6 shadow-[var(--shadow-sm)]">
        <h2 className="text-md font-semibold text-[var(--ink)] mb-3" style={{ fontFamily: "var(--font-display)" }}>
          Ask a new question
        </h2>
        <form onSubmit={handleAsk} className="flex gap-3">
          <Input
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            placeholder="e.g. What is the attendance requirement?"
            className="flex-1"
          />
          <Button type="submit" variant="primary" disabled={!question.trim()}>
            <Send className="h-4 w-4" aria-hidden />
            <span>Ask</span>
          </Button>
        </form>

        {/* Suggested Quick Questions */}
        <div className="mt-4 flex flex-wrap items-center gap-2">
          <span className="text-[10px] font-bold uppercase tracking-wider text-[var(--ink-ghost)] mr-1">
            Try asking:
          </span>
          {QUICK_QUESTIONS.map((q) => (
            <button
              key={q}
              type="button"
              onClick={() => handleQuickAsk(q)}
              className="rounded-full border border-[var(--edge-strong)] bg-[var(--canvas)] px-3 py-1.5 text-left text-xs text-[var(--ink-muted)] transition-all hover:border-[var(--primary-muted)] hover:bg-[var(--primary-faint)] hover:text-[var(--primary)]"
            >
              {q}
            </button>
          ))}
        </div>
      </section>

      {/* Double Column Layout */}
      <div className="grid gap-6 md:grid-cols-2">
        {/* Recent Conversations */}
        <section className="rounded-[var(--radius-lg)] border border-[var(--edge)] bg-[var(--canvas-raised)] p-6 shadow-[var(--shadow-sm)] flex flex-col">
          <div className="flex items-center justify-between border-b border-[var(--edge)] pb-3 mb-4">
            <div className="flex items-center gap-2">
              <MessageSquareText className="h-[18px] w-[18px] text-[var(--primary)]" aria-hidden />
              <h2 className="text-md font-semibold text-[var(--ink)]" style={{ fontFamily: "var(--font-display)" }}>
                Recent Chats
              </h2>
            </div>
            <Link href="/chat">
              <Button size="sm" variant="ghost" className="text-xs">
                View all
              </Button>
            </Link>
          </div>

          <div className="flex-1 space-y-2">
            {conversations.length === 0 ? (
              <div className="text-center py-6 text-xs text-[var(--ink-ghost)]">
                No recent conversations.
              </div>
            ) : (
              conversations.map((convo) => (
                <Link
                  key={convo.id}
                  href={`/chat/${convo.id}`}
                  className="flex items-center justify-between rounded-[var(--radius-sm)] border border-[var(--edge)] p-3 hover:bg-[var(--canvas-inset)] hover:border-[var(--edge-strong)] transition-all no-underline text-[var(--ink)]"
                >
                  <span className="truncate text-sm font-medium pr-3">{convo.title}</span>
                  <ArrowRight className="h-4 w-4 text-[var(--ink-ghost)] shrink-0" />
                </Link>
              ))
            )}
          </div>
        </section>

        {/* Documents Summary */}
        <section className="rounded-[var(--radius-lg)] border border-[var(--edge)] bg-[var(--canvas-raised)] p-6 shadow-[var(--shadow-sm)] flex flex-col">
          <div className="flex items-center justify-between border-b border-[var(--edge)] pb-3 mb-4">
            <div className="flex items-center gap-2">
              <FileText className="h-[18px] w-[18px] text-[var(--primary)]" aria-hidden />
              <h2 className="text-md font-semibold text-[var(--ink)]" style={{ fontFamily: "var(--font-display)" }}>
                Document Library
              </h2>
            </div>
            <Link href="/documents">
              <Button size="sm" variant="ghost" className="text-xs">
                Manage
              </Button>
            </Link>
          </div>

          <div className="flex-1 space-y-2">
            {documents.length === 0 ? (
              <div className="text-center py-6 text-xs text-[var(--ink-ghost)]">
                No documents uploaded yet.
              </div>
            ) : (
              documents.map((doc) => (
                <Link
                  key={doc.id}
                  href={`/documents/${doc.id}`}
                  className="flex items-center justify-between rounded-[var(--radius-sm)] border border-[var(--edge)] p-3 hover:bg-[var(--canvas-inset)] hover:border-[var(--edge-strong)] transition-all no-underline text-[var(--ink)]"
                >
                  <div className="min-w-0 pr-3">
                    <p className="truncate text-sm font-medium">{doc.title}</p>
                    <span className="text-[10px] text-[var(--ink-faint)]">
                      {doc.original_filename}
                    </span>
                  </div>
                  <span
                    className={`shrink-0 rounded-full border px-2 py-0.5 text-[9px] font-bold uppercase tracking-wider ${
                      doc.status === "ACTIVE"
                        ? "border-[var(--success)] bg-[var(--success-faint)] text-[var(--success)]"
                        : doc.status === "FAILED"
                        ? "border-[var(--danger)] bg-[var(--danger-faint)] text-[var(--danger)]"
                        : "border-[var(--edge-strong)] bg-[var(--canvas-inset)] text-[var(--ink-faint)]"
                    }`}
                  >
                    {doc.status}
                  </span>
                </Link>
              ))
            )}
          </div>
        </section>
      </div>
    </div>
  );
}
