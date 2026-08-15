"use client";

/**
 * Public demo chat: ask grounded questions about the single pre-indexed demo
 * document, no upload or account required.
 *
 * This component is only rendered when the backend reports demo mode active
 * (via `/api/demo/info`). It reuses the DocMind design system (shadcn-style
 * primitives + design tokens) and the same message/citation rendering as the
 * authenticated dashboard chat.
 */

import { useEffect, useRef, useState } from "react";
import { FileText, Loader2, MessageSquareText, Send } from "lucide-react";

import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ApiError } from "@/lib/api";
import {
  askDemoQuestion,
  type DemoCitation,
  type DemoInfo,
} from "@/lib/demo";
import { cn } from "@/lib/utils";

/** Predefined, clickable questions surfaced near the chat input. */
const EXAMPLE_QUESTIONS = [
  "What is DocMind designed to do?",
  "What were the three evaluation configurations?",
  "What were the retrieval recall and answer accuracy of Hybrid + Reranking?",
  "How much did Hybrid Retrieval improve recall compared with Baseline Search?",
  "Was Hybrid + Reranking within the acceptable latency limit, and why?",
];

interface DemoMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  citations: DemoCitation[];
}

function CitationList({ citations }: { citations: DemoCitation[] }) {
  if (citations.length === 0) return null;
  return (
    <div className="mt-3 border-t border-[var(--edge)] pt-3">
      <p className="mb-2 text-[11px] font-semibold uppercase tracking-[0.1em] text-[var(--ink-faint)]">
        Sources ({citations.length})
      </p>
      <ul className="space-y-1.5">
        {citations.map((citation, i) => {
          const label =
            citation.section ??
            (citation.page_number != null
              ? `p.\u00A0${citation.page_number}`
              : null);
          return (
            <li
              key={`${citation.chunk_id}-${i}`}
              className="flex items-center gap-1.5 text-xs text-[var(--ink-muted)]"
            >
              <span className="h-1.5 w-1.5 rounded-full bg-[var(--accent-muted)] shrink-0" />
              <span className="font-medium text-[var(--ink)]">
                {citation.document_title}
              </span>
              {label && (
                <span className="text-[var(--ink-faint)]">· {label}</span>
              )}
            </li>
          );
        })}
      </ul>
    </div>
  );
}

export function DemoChat({ info }: { info: DemoInfo }) {
  const [messages, setMessages] = useState<DemoMessage[]>([]);
  const [question, setQuestion] = useState("");
  const [asking, setAsking] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages, asking]);

  async function ask(raw: string) {
    const trimmed = raw.trim();
    if (!trimmed || asking) return;
    setAsking(true);
    setError(null);
    const userMessage: DemoMessage = {
      id: `user-${Date.now()}`,
      role: "user",
      content: trimmed,
      citations: [],
    };
    setMessages((current) => [...current, userMessage]);
    try {
      const response = await askDemoQuestion(trimmed);
      const assistantMessage: DemoMessage = {
        id: `assistant-${Date.now()}`,
        role: "assistant",
        content: response.answer,
        citations: response.citations,
      };
      setMessages((current) => [...current, assistantMessage]);
    } catch (err) {
      setError(
        err instanceof ApiError ? err.message : "Unable to get an answer.",
      );
    } finally {
      setAsking(false);
    }
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const trimmed = question.trim();
    if (!trimmed || asking) return;
    setQuestion("");
    void ask(trimmed);
  }

  if (info.status !== "ready") {
    return (
      <section className="mx-auto w-full max-w-2xl px-6 py-12">
        <Alert variant="error">
          The demo index has not been built yet. The administrator must run{" "}
          <code>python -m scripts.build_demo_index</code> from the backend
          directory before the demo can answer questions.
        </Alert>
      </section>
    );
  }

  return (
    <section className="mx-auto w-full max-w-2xl px-6 py-10 animate-page-in">
      {/* Demo document card */}
      <div className="flex items-center gap-3 rounded-[var(--radius-lg)] border border-[var(--edge)] bg-[var(--canvas-raised)] p-5 shadow-[var(--shadow-sm)]">
        <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-[var(--radius-sm)] bg-[var(--accent-faint)] text-[var(--accent)]">
          <FileText className="h-5 w-5" aria-hidden />
        </span>
        <div className="min-w-0">
          <p className="text-[11px] font-semibold uppercase tracking-[0.1em] text-[var(--ink-faint)]">
            Demo Document
          </p>
          <p className="truncate text-[var(--ink)]" style={{ fontFamily: "var(--font-display)" }}>
            {info.document_title}
          </p>
          <p className="text-xs text-[var(--ink-faint)]">
            Ask questions about this document.
          </p>
        </div>
        <span className="ml-auto shrink-0 rounded-full border border-[var(--accent-muted)] bg-[var(--accent-faint)] px-2.5 py-0.5 text-[11px] font-semibold uppercase tracking-wide text-[var(--accent)]">
          Public demo
        </span>
      </div>

      {/* Chat panel */}
      <div className="mt-5 flex flex-col rounded-[var(--radius-lg)] border border-[var(--edge)] bg-[var(--canvas-raised)] p-6 shadow-[var(--shadow-sm)]">
        <div className="flex items-center gap-2.5">
          <MessageSquareText className="h-4 w-4 text-[var(--accent)]" aria-hidden />
          <h2
            className="text-lg text-[var(--ink)]"
            style={{ fontFamily: "var(--font-display)" }}
          >
            Ask a question
          </h2>
        </div>

        {/* Chat history */}
        <div className="mt-5 space-y-4">
          {messages.length === 0 && !asking && (
            <div className="rounded-[var(--radius-md)] border border-dashed border-[var(--edge-strong)] p-6 text-center">
              <p
                className="text-[var(--ink-faint)]"
                style={{ fontFamily: "var(--font-display)" }}
              >
                Ask a question to begin.
              </p>
              <p className="mt-1 text-sm text-[var(--ink-ghost)]">
                Answers are grounded in the demo document — never general
                knowledge.
              </p>
            </div>
          )}

          {messages.map((message) => (
            <div
              key={message.id}
              className={cn(
                "rounded-[var(--radius-md)] border p-4",
                message.role === "user"
                  ? "border-[var(--accent-muted)] bg-[var(--accent-faint)] ml-8"
                  : "border-[var(--edge)] bg-[var(--canvas-inset)] mr-8 border-l-[3px] border-l-[var(--ink)]",
              )}
            >
              <p className="text-[11px] font-semibold uppercase tracking-[0.1em] text-[var(--ink-faint)]">
                {message.role === "user" ? "You" : "DocMind"}
              </p>
              <p className="mt-1.5 whitespace-pre-wrap text-sm leading-relaxed text-[var(--ink)]">
                {message.content
                  .replace(/\s*Sources:\s*\[[\d,\s]+\]\s*$/, "")
                  .trim()}
              </p>
              {message.role === "assistant" && (
                <CitationList citations={message.citations} />
              )}
            </div>
          ))}

          {asking && (
            <div
              className="flex items-center gap-2.5 rounded-[var(--radius-md)] border border-[var(--edge)] bg-[var(--canvas-inset)] p-4 mr-8 border-l-[3px] border-l-[var(--accent)] text-sm text-[var(--ink-muted)]"
              role="status"
            >
              <Loader2
                className="h-4 w-4 text-[var(--accent)]"
                style={{ animation: "spin 0.7s linear infinite" }}
                aria-hidden
              />
              Retrieving relevant sections…
            </div>
          )}
          <div ref={bottomRef} />
        </div>

        {error && (
          <Alert className="mt-4" variant="error">
            {error}
          </Alert>
        )}

        {/* Try asking */}
        <div className="mt-5 border-t border-[var(--edge)] pt-5">
          <p className="text-[11px] font-semibold uppercase tracking-[0.1em] text-[var(--ink-faint)]">
            Try asking
          </p>
          <div className="mt-3 flex flex-wrap gap-2">
            {EXAMPLE_QUESTIONS.map((example) => (
              <button
                key={example}
                type="button"
                onClick={() => void ask(example)}
                disabled={asking}
                className="rounded-full border border-[var(--edge-strong)] bg-[var(--canvas-raised)] px-3.5 py-1.5 text-left text-xs text-[var(--ink-muted)] transition-all duration-150 hover:border-[var(--accent)] hover:bg-[var(--accent-faint)] hover:text-[var(--accent)] disabled:pointer-events-none disabled:opacity-45"
              >
                {example}
              </button>
            ))}
          </div>
        </div>

        {/* Input */}
        <form
          onSubmit={handleSubmit}
          className="mt-5 flex items-center gap-3 border-t border-[var(--edge)] pt-5"
        >
          <Input
            className="flex-1"
            placeholder="Ask a question about this document…"
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            disabled={asking}
            maxLength={2000}
          />
          <Button
            type="submit"
            variant="accent"
            disabled={!question.trim() || asking}
            className="self-end"
          >
            {asking ? (
              <Loader2
                className="h-4 w-4"
                style={{ animation: "spin 0.7s linear infinite" }}
                aria-hidden
              />
            ) : (
              <Send className="h-4 w-4" aria-hidden />
            )}
            Ask
          </Button>
        </form>
      </div>
    </section>
  );
}