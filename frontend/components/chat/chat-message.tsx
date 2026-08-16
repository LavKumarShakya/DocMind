"use client";

import { ThumbsUp, ThumbsDown, FileText } from "lucide-react";
import { useState } from "react";
import { submitFeedback } from "@/lib/feedback";
import { cn } from "@/lib/utils";

export interface CitationItem {
  chunk_id?: string | null;
  document_id?: string | null;
  document_title: string;
  page_number: number | null;
  section: string | null;
  relevance_score?: number | null;
  text?: string | null;
}

interface ChatMessageProps {
  id: string;
  role: "user" | "assistant";
  content: string;
  citations?: CitationItem[];
  onSelectSource?: (citation: CitationItem) => void;
  showFeedback?: boolean;
}

export function ChatMessage({
  id,
  role,
  content,
  citations = [],
  onSelectSource,
  showFeedback = true,
}: ChatMessageProps) {
  const [sending, setSending] = useState(false);
  const [feedbackRating, setFeedbackRating] = useState<number | null>(null);

  async function rate(rating: number) {
    if (sending || feedbackRating !== null) return;
    setSending(true);
    try {
      await submitFeedback({ message_id: id, rating });
      setFeedbackRating(rating);
    } catch {
      // Ignore feedback submission errors in UI silently
    } finally {
      setSending(false);
    }
  }

  // Clean the text from tailing sources format if present (e.g. Sources: [1, 2])
  const cleanContent = content
    .replace(/\s*Sources:\s*\[[\d,\s]+\]\s*$/, "")
    .trim();

  // Helper to render text with clickable citation badges
  const renderMessageContent = () => {
    if (role === "user") {
      return <p className="whitespace-pre-wrap text-sm leading-relaxed text-[var(--ink)]">{cleanContent}</p>;
    }

    // Split text by [number] pattern to make inline citations clickable
    const parts = cleanContent.split(/(\[\d+\])/g);
    return (
      <p className="whitespace-pre-wrap text-sm leading-relaxed text-[var(--ink)]">
        {parts.map((part, index) => {
          const match = part.match(/^\[(\d+)\]$/);
          if (match) {
            const citeNum = parseInt(match[1], 10);
            const citation = citations[citeNum - 1];
            if (citation) {
              return (
                <button
                  key={index}
                  type="button"
                  onClick={() => onSelectSource?.(citation)}
                  className="mx-0.5 inline-flex h-4 min-w-4 items-center justify-center rounded bg-[var(--primary-faint)] px-1 text-[10px] font-bold text-[var(--primary)] transition-colors hover:bg-[var(--primary-muted)] hover:text-white"
                  title={`${citation.document_title} - Page ${citation.page_number ?? "N/A"}`}
                >
                  {citeNum}
                </button>
              );
            }
          }
          return part;
        })}
      </p>
    );
  };

  return (
    <div
      className={cn(
        "flex flex-col gap-2 rounded-[var(--radius-lg)] border p-5 shadow-[var(--shadow-sm)] transition-all duration-200 animate-page-in",
        role === "user"
          ? "border-[var(--primary-muted)] bg-[var(--primary-faint)]/40 ml-12"
          : "border-[var(--edge)] bg-[var(--canvas-raised)] mr-12 border-l-4 border-l-[var(--ink)]"
      )}
    >
      <div className="flex items-center justify-between">
        <span className="text-[10px] font-bold uppercase tracking-[0.15em] text-[var(--ink-faint)]">
          {role === "user" ? "You" : "DocMind"}
        </span>
      </div>

      <div className="mt-1">{renderMessageContent()}</div>

      {role === "assistant" && (
        <>
          {/* Citation List at bottom of message */}
          {citations.length > 0 && (
            <div className="mt-4 border-t border-[var(--edge)] pt-3">
              <p className="mb-2 text-[10px] font-bold uppercase tracking-[0.1em] text-[var(--ink-faint)]">
                Sources
              </p>
              <div className="flex flex-wrap gap-2">
                {citations.map((citation, i) => (
                  <button
                    key={i}
                    type="button"
                    onClick={() => onSelectSource?.(citation)}
                    className="flex items-center gap-1.5 rounded-full border border-[var(--edge)] bg-[var(--canvas)] px-3 py-1 text-left text-xs text-[var(--ink-muted)] transition-all hover:border-[var(--primary-muted)] hover:bg-[var(--primary-faint)] hover:text-[var(--primary)]"
                  >
                    <span className="flex h-3.5 w-3.5 items-center justify-center rounded-full bg-[var(--ink-ghost)] text-[9px] font-bold text-[var(--ink-muted)]">
                      {i + 1}
                    </span>
                    <span className="truncate max-w-[150px] font-medium text-[var(--ink)]">
                      {citation.document_title}
                    </span>
                    {citation.page_number != null && (
                      <span className="text-[var(--ink-faint)]">· p.{citation.page_number}</span>
                    )}
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Feedback buttons */}
          {showFeedback && (
            <div className="mt-3 flex items-center gap-2 text-[10px] font-semibold text-[var(--ink-faint)] uppercase tracking-wide">
              <span>Was this helpful?</span>
              <button
                type="button"
                onClick={() => rate(5)}
                disabled={sending || feedbackRating !== null}
                className={cn(
                  "inline-flex items-center gap-1 rounded-full border px-2 py-0.5 transition-all duration-150",
                  feedbackRating === 5
                    ? "border-[var(--success)] bg-[var(--success-faint)] text-[var(--success)]"
                    : "border-[var(--edge)] hover:border-[var(--success)] hover:bg-[var(--success-faint)] hover:text-[var(--success)]"
                )}
                aria-label="Thumbs up helpful"
              >
                <ThumbsUp className="h-3 w-3" aria-hidden />
              </button>
              <button
                type="button"
                onClick={() => rate(1)}
                disabled={sending || feedbackRating !== null}
                className={cn(
                  "inline-flex items-center gap-1 rounded-full border px-2 py-0.5 transition-all duration-150",
                  feedbackRating === 1
                    ? "border-[var(--danger)] bg-[var(--danger-faint)] text-[var(--danger)]"
                    : "border-[var(--edge)] hover:border-[var(--danger)] hover:bg-[var(--danger-faint)] hover:text-[var(--danger)]"
                )}
                aria-label="Thumbs down unhelpful"
              >
                <ThumbsDown className="h-3 w-3" aria-hidden />
              </button>
              {feedbackRating !== null && (
                <span className="text-[var(--success)] lowercase tracking-normal font-normal">
                  Thanks for your feedback!
                </span>
              )}
            </div>
          )}
        </>
      )}
    </div>
  );
}
