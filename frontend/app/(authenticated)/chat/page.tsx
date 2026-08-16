"use client";

import { useEffect, useState, Suspense } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { MessageSquareText, Loader2 } from "lucide-react";

import { Alert } from "@/components/ui/alert";
import { ChatInput } from "@/components/chat/chat-input";
import { askQuestion } from "@/lib/chat";
import { useToast } from "@/components/common/toast";
import { listConversations } from "@/lib/conversations";

const SUGGESTED_QUESTIONS = [
  "What is the minimum attendance requirement?",
  "What are the examination rules?",
  "Who is eligible for scholarship?",
];

function ChatHomeContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { toast } = useToast();

  const [asking, setAsking] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const initialQuery = searchParams.get("q");

  useEffect(() => {
    if (initialQuery) {
      void handleSend(initialQuery);
    }
  }, [initialQuery]);

  const handleSend = async (message: string) => {
    setAsking(true);
    setError(null);
    try {
      const response = await askQuestion(message);
      // Success: redirect to the newly created conversation detail
      router.push(`/chat/${response.conversation_id}`);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Unable to initiate chat."
      );
      toast("Unable to send question.", "error");
      setAsking(false);
    }
  };

  return (
    <div className="h-full flex flex-col justify-between p-6 max-w-3xl mx-auto">
      {/* Empty state overview */}
      <div className="flex-1 flex flex-col justify-center items-center text-center space-y-6">
        <div className="flex h-12 w-12 items-center justify-center rounded-full bg-[var(--primary-faint)] text-[var(--primary)]">
          <MessageSquareText className="h-6 w-6" aria-hidden />
        </div>
        <div className="space-y-2">
          <h1 className="text-2xl font-semibold text-[var(--ink)]" style={{ fontFamily: "var(--font-display)" }}>
            Ask DocMind
          </h1>
          <p className="text-sm text-[var(--ink-faint)] max-w-md">
            Query university policy documents. Answers are grounded and citations are verifiable.
          </p>
        </div>

        {asking && (
          <div className="flex items-center gap-2 text-sm text-[var(--primary)] font-semibold animate-pulse">
            <Loader2 className="h-4 w-4" style={{ animation: "spin 0.7s linear infinite" }} />
            Starting conversation & searching sources…
          </div>
        )}

        {error && (
          <Alert variant="error" className="max-w-md w-full text-left">
            {error}
          </Alert>
        )}

        {!asking && (
          <div className="max-w-md w-full pt-4">
            <span className="text-[10px] font-bold uppercase tracking-wider text-[var(--ink-ghost)] block mb-3">
              Suggested questions
            </span>
            <div className="flex flex-wrap justify-center gap-2">
              {SUGGESTED_QUESTIONS.map((q) => (
                <button
                  key={q}
                  type="button"
                  onClick={() => void handleSend(q)}
                  className="rounded-full border border-[var(--edge-strong)] bg-[var(--canvas-raised)] px-4 py-2 text-xs text-[var(--ink-muted)] hover:border-[var(--primary-muted)] hover:bg-[var(--primary-faint)] hover:text-[var(--primary)] transition-all text-left"
                >
                  {q}
                </button>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Input container at bottom */}
      <div className="border-t border-[var(--edge)] pt-4 bg-[var(--canvas)] shrink-0">
        <ChatInput onSend={(val) => void handleSend(val)} disabled={asking} />
      </div>
    </div>
  );
}

export default function ChatHomePage() {
  return (
    <Suspense
      fallback={
        <div className="h-full flex items-center justify-center">
          <Loader2 className="h-8 w-8 text-[var(--primary)] animate-spin" />
        </div>
      }
    >
      <ChatHomeContent />
    </Suspense>
  );
}
export const dynamic = "force-dynamic";
