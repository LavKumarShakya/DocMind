"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import { useParams, useRouter } from "next/navigation";
import { MessageSquareText, Loader2, ArrowLeft } from "lucide-react";

import { Alert } from "@/components/ui/alert";
import { ChatMessage, type CitationItem } from "@/components/chat/chat-message";
import { ChatInput } from "@/components/chat/chat-input";
import { SourcePanel } from "@/components/chat/source-panel";
import { getConversation, type MessageDetail } from "@/lib/conversations";
import { askQuestion } from "@/lib/chat";
import { useToast } from "@/components/common/toast";
import { ApiError } from "@/lib/api";

export default function ChatDetailPage() {
  const params = useParams();
  const router = useRouter();
  const { toast } = useToast();
  const conversationId = params?.id as string;

  const [messages, setMessages] = useState<MessageDetail[]>([]);
  const [loading, setLoading] = useState(true);
  const [asking, setAsking] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lastQuestion, setLastQuestion] = useState<string | null>(null);
  const [title, setTitle] = useState("");
  const [activeSource, setActiveSource] = useState<CitationItem | null>(null);

  const chatEndRef = useRef<HTMLDivElement>(null);

  const fetchDetails = useCallback(async () => {
    try {
      const details = await getConversation(conversationId);
      setMessages(details.messages);
      setTitle(details.title);
    } catch {
      toast("Unable to load chat details.", "error");
      router.push("/chat");
    } finally {
      setLoading(false);
    }
  }, [conversationId, router, toast]);

  useEffect(() => {
    if (conversationId) {
      void fetchDetails();
    }
  }, [conversationId, fetchDetails]);

  // Auto-scroll logic
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, asking]);

  const handleAsk = async (text: string) => {
    setAsking(true);
    setError(null);
    setLastQuestion(text);

    // Optimistic User Message
    const userMsg: MessageDetail = {
      id: `user-temp-${Date.now()}`,
      role: "USER",
      content: text,
      created_at: new Date().toISOString(),
      citations: [],
    };
    setMessages((prev) => [...prev, userMsg]);

    try {
      const res = await askQuestion(text, conversationId);
      // Replace optimistic message and append assistant message
      const assistantMsg: MessageDetail = {
        id: res.message_id,
        role: "ASSISTANT",
        content: res.answer,
        created_at: new Date().toISOString(),
        citations: res.citations.map((c) => ({
          chunk_id: c.chunk_id,
          document_id: c.document_id,
          document_title: c.document_title,
          page_number: c.page_number,
          section: c.section,
          relevance_score: c.relevance_score,
        })),
      };
      setMessages((prev) => {
        // remove optimistic one and put actual
        const filtered = prev.filter((m) => m.id !== userMsg.id);
        return [...filtered, userMsg, assistantMsg];
      });
    } catch (err) {
      if (err instanceof ApiError) {
        if (err.code === "LLM_RATE_LIMITED") {
          setError("DocMind's AI service is temporarily rate limited. Please try again shortly.");
        } else if (err.code === "LLM_UNAVAILABLE") {
          setError("DocMind's AI service is temporarily unavailable. Please try again.");
        } else {
          setError(err.message);
        }
      } else {
        setError("Unable to get an answer.");
      }
      // Rollback user optimistic message on failure so chat history stays clean
      setMessages((prev) => prev.filter((m) => m.id !== userMsg.id));
    } finally {
      setAsking(false);
    }
  };

  if (loading) {
    return (
      <div className="h-full flex flex-col justify-center items-center">
        <Loader2 className="h-8 w-8 text-[var(--primary)] animate-spin mb-2" />
        <span className="text-xs text-[var(--ink-faint)]">Loading conversation…</span>
      </div>
    );
  }

  return (
    <div className="h-full flex flex-col justify-between p-6 max-w-3xl mx-auto relative">
      {/* Header */}
      <div className="flex items-center gap-3 border-b border-[var(--edge)] pb-4 shrink-0">
        <button
          type="button"
          onClick={() => router.push("/chat")}
          className="md:hidden p-1 rounded hover:bg-[var(--canvas-inset)] text-[var(--ink-muted)]"
          aria-label="Back to chat overview"
        >
          <ArrowLeft className="h-5 w-5" aria-hidden />
        </button>
        <div className="min-w-0">
          <span className="text-[9px] font-bold uppercase tracking-wider text-[var(--ink-faint)]">
            Active Chat
          </span>
          <h1 className="text-md font-semibold text-[var(--ink)] truncate" style={{ fontFamily: "var(--font-display)" }}>
            {title || "Conversation"}
          </h1>
        </div>
      </div>

      {/* Messages Window */}
      <div className="flex-1 overflow-y-auto py-6 space-y-4 pr-1">
        {messages.map((message) => (
          <ChatMessage
            key={message.id}
            id={message.id}
            role={message.role === "USER" ? "user" : "assistant"}
            content={message.content}
            citations={message.citations.map((c) => ({
              chunk_id: c.chunk_id,
              document_id: c.document_id,
              document_title: c.document_title ?? "Unknown source",
              page_number: c.page_number,
              section: c.section,
              relevance_score: c.relevance_score,
            }))}
            onSelectSource={setActiveSource}
          />
        ))}

        {asking && (
          <div
            className="flex items-center gap-2.5 rounded-[var(--radius-md)] border border-[var(--edge)] bg-[var(--canvas-raised)] p-4 mr-12 border-l-4 border-l-[var(--primary)] text-sm text-[var(--ink-muted)] animate-pulse"
            role="status"
          >
            <Loader2
              className="h-4 w-4 text-[var(--primary)] animate-spin"
              aria-hidden
            />
            Searching sources & preparing answer…
          </div>
        )}

        {error && (
          <Alert className="mt-4 flex flex-col gap-2" variant="error">
            <div>{error}</div>
            {lastQuestion && (
              <button
                type="button"
                onClick={() => void handleAsk(lastQuestion)}
                className="text-xs self-start underline font-semibold text-[var(--danger)] hover:text-[var(--danger-muted)]"
              >
                Retry question
              </button>
            )}
          </Alert>
        )}
        <div ref={chatEndRef} />
      </div>

      {/* Input container */}
      <div className="border-t border-[var(--edge)] pt-4 bg-[var(--canvas)] shrink-0">
        <ChatInput onSend={(val) => void handleAsk(val)} disabled={asking} placeholder="Type a follow-up question..." />
      </div>

      {/* Side details panel */}
      <SourcePanel citation={activeSource} onClose={() => setActiveSource(null)} />
    </div>
  );
}
export const dynamic = "force-dynamic";
