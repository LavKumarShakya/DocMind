"use client";

import { useEffect, useRef, useState } from "react";
import { FileText, Loader2, MessageSquareText, Download } from "lucide-react";

import { Alert } from "@/components/ui/alert";
import { ChatMessage, type CitationItem } from "@/components/chat/chat-message";
import { ChatInput } from "@/components/chat/chat-input";
import { SourcePanel } from "@/components/chat/source-panel";
import { askDemoQuestion, type DemoInfo } from "@/lib/demo";
import { ApiError } from "@/lib/api";

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
  citations: CitationItem[];
}

export function DemoChat({ info }: { info: DemoInfo }) {
  const [messages, setMessages] = useState<DemoMessage[]>([]);
  const [asking, setAsking] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [activeSource, setActiveSource] = useState<CitationItem | null>(null);
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
        citations: response.citations.map((c) => ({
          chunk_id: c.chunk_id,
          document_id: c.document_id,
          document_title: c.document_title,
          page_number: c.page_number,
          section: c.section,
          relevance_score: c.relevance_score,
        })),
      };
      setMessages((current) => [...current, assistantMessage]);
    } catch (err) {
      setError(
        err instanceof ApiError ? err.message : "Unable to get an answer."
      );
    } finally {
      setAsking(false);
    }
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
    <section className="mx-auto w-full max-w-3xl px-4 py-8 sm:px-6 animate-page-in">
      {/* Demo document card */}
      <div className="flex flex-wrap items-center justify-between gap-4 rounded-[var(--radius-lg)] border border-[var(--edge)] bg-[var(--canvas-raised)] p-5 shadow-[var(--shadow-sm)]">
        <div className="flex items-center gap-3.5 min-w-0">
          <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-[var(--radius-md)] bg-[var(--primary-faint)] text-[var(--primary)]">
            <FileText className="h-5 w-5" aria-hidden />
          </span>
          <div className="min-w-0">
            <span className="text-[9px] font-bold uppercase tracking-wider text-[var(--ink-faint)]">
              Demo Mode Active
            </span>
            <h3 className="truncate text-md font-semibold text-[var(--ink)]" style={{ fontFamily: "var(--font-display)" }}>
              {info.document_title}
            </h3>
            <p className="text-xs text-[var(--ink-faint)]">
              Ask questions about this university system document.
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <a
            href="/DocMind_Public_Demo_Test_Document.pdf"
            download
            className="inline-flex items-center gap-1.5 rounded-full border border-[var(--edge-strong)] bg-[var(--canvas-raised)] px-3 py-1 text-[10px] font-bold uppercase tracking-wider text-[var(--ink-muted)] hover:border-[var(--primary-muted)] hover:bg-[var(--primary-faint)] hover:text-[var(--primary)] transition-all no-underline cursor-pointer"
          >
            <Download className="h-3.5 w-3.5" aria-hidden />
            Download PDF
          </a>
          <span className="rounded-full border border-[var(--primary-muted)] bg-[var(--primary-faint)] px-3 py-1 text-[10px] font-bold uppercase tracking-wider text-[var(--primary)]">
            Public Demo
          </span>
        </div>
      </div>

      {/* Chat panel */}
      <div className="mt-5 flex flex-col rounded-[var(--radius-lg)] border border-[var(--edge)] bg-[var(--canvas-raised)] p-6 shadow-[var(--shadow-sm)]">
        <div className="flex items-center justify-between border-b border-[var(--edge)] pb-4">
          <div className="flex items-center gap-2.5">
            <MessageSquareText className="h-[18px] w-[18px] text-[var(--primary)]" aria-hidden />
            <h2 className="text-md font-semibold text-[var(--ink)]" style={{ fontFamily: "var(--font-display)" }}>
              Grounded Chat
            </h2>
          </div>
        </div>

        {/* Chat history */}
        <div className="mt-6 min-h-[300px] max-h-[500px] overflow-y-auto space-y-4 pr-1">
          {messages.length === 0 && !asking && (
            <div className="flex flex-col items-center justify-center rounded-[var(--radius-md)] border border-dashed border-[var(--edge-strong)] p-10 text-center">
              <MessageSquareText className="h-8 w-8 text-[var(--ink-ghost)] mb-2" aria-hidden />
              <p className="text-sm font-semibold text-[var(--ink-faint)]" style={{ fontFamily: "var(--font-display)" }}>
                Start a conversation.
              </p>
              <p className="mt-1 max-w-sm text-xs text-[var(--ink-ghost)]">
                Answers are grounded strictly in the demo document, citations are verifiable.
              </p>
            </div>
          )}

          {messages.map((message) => (
            <ChatMessage
              key={message.id}
              id={message.id}
              role={message.role}
              content={message.content}
              citations={message.citations}
              onSelectSource={setActiveSource}
              showFeedback={false} // Hide backend feedback submission in public demo mode
            />
          ))}

          {asking && (
            <div
              className="flex items-center gap-2.5 rounded-[var(--radius-md)] border border-[var(--edge)] bg-[var(--canvas-inset)] p-4 mr-12 border-l-4 border-l-[var(--primary)] text-sm text-[var(--ink-muted)] animate-pulse"
              role="status"
            >
              <Loader2
                className="h-4 w-4 text-[var(--primary)]"
                style={{ animation: "spin 0.7s linear infinite" }}
                aria-hidden
              />
              Searching documents & preparing answer…
            </div>
          )}
          <div ref={bottomRef} />
        </div>

        {error && (
          <Alert className="mt-4" variant="error">
            {error}
          </Alert>
        )}

        {/* Try asking Section */}
        <div className="mt-6 border-t border-[var(--edge)] pt-5">
          <span className="text-[10px] font-bold uppercase tracking-wider text-[var(--ink-faint)]">
            Try asking
          </span>
          <div className="mt-2.5 flex flex-wrap gap-2">
            {EXAMPLE_QUESTIONS.map((example) => (
              <button
                key={example}
                type="button"
                onClick={() => void ask(example)}
                disabled={asking}
                className="rounded-full border border-[var(--edge-strong)] bg-[var(--canvas-raised)] px-3.5 py-1.5 text-left text-xs text-[var(--ink-muted)] transition-all hover:border-[var(--primary-muted)] hover:bg-[var(--primary-faint)] hover:text-[var(--primary)] disabled:pointer-events-none disabled:opacity-45"
              >
                {example}
              </button>
            ))}
          </div>
        </div>

        {/* Input */}
        <div className="mt-6">
          <ChatInput
            onSend={(val) => void ask(val)}
            disabled={asking}
            placeholder="Ask a question about this document..."
          />
        </div>
      </div>

      {/* Side panel for details */}
      <SourcePanel
        citation={activeSource}
        onClose={() => setActiveSource(null)}
      />
    </section>
  );
}