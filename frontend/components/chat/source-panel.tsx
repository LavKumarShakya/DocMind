"use client";

import { X, FileText, BarChart2, Shield } from "lucide-react";
import { useEffect, useRef } from "react";
import { type CitationItem } from "./chat-message";
import { cn } from "@/lib/utils";

interface SourcePanelProps {
  citation: CitationItem | null;
  onClose: () => void;
}

export function SourcePanel({ citation, onClose }: SourcePanelProps) {
  const panelRef = useRef<HTMLDivElement>(null);

  // Close on Escape key press
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape" && citation) {
        onClose();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [citation, onClose]);

  if (!citation) return null;

  return (
    <>
      {/* Backdrop for mobile */}
      <div
        className="fixed inset-0 z-40 bg-[var(--ink)]/20 lg:hidden"
        style={{ animation: "overlay-fade-in 0.2s ease-out" }}
        onClick={onClose}
        aria-hidden
      />

      {/* Side Panel / Bottom Drawer */}
      <div
        ref={panelRef}
        role="dialog"
        aria-labelledby="source-panel-title"
        className={cn(
          "fixed z-50 flex flex-col border-[var(--edge)] bg-[var(--canvas-raised)] shadow-[var(--shadow-lg)] transition-transform duration-250 ease-out",
          // Desktop: right panel
          "lg:right-0 lg:top-14 lg:h-[calc(100vh-56px)] lg:w-96 lg:border-l lg:translate-x-0",
          // Mobile: bottom drawer
          "bottom-0 left-0 right-0 h-[400px] rounded-t-[var(--radius-lg)] border-t translate-y-0",
          // Toggle position for desktop vs mobile layout structure integration
          "lg:bottom-auto lg:left-auto lg:rounded-none"
        )}
        style={{
          animation: window.innerWidth >= 1024 
            ? "slide-in-right 0.25s ease-out" 
            : "slide-in-bottom 0.25s ease-out"
        }}
      >
        {/* Header */}
        <div className="flex items-center justify-between border-b border-[var(--edge)] px-5 py-4">
          <div className="flex items-center gap-2">
            <FileText className="h-[18px] w-[18px] text-[var(--primary)]" aria-hidden />
            <h2
              id="source-panel-title"
              className="text-md font-semibold text-[var(--ink)]"
              style={{ fontFamily: "var(--font-display)" }}
            >
              Source Evidence
            </h2>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-[var(--radius-sm)] p-1 text-[var(--ink-ghost)] hover:bg-[var(--canvas-inset)] hover:text-[var(--ink)] transition-colors"
            aria-label="Close panel"
          >
            <X className="h-4 w-4" aria-hidden />
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-6 space-y-6">
          {/* Document Header */}
          <div>
            <span className="text-[10px] font-bold uppercase tracking-wider text-[var(--ink-faint)]">
              Document
            </span>
            <h3 className="mt-1 text-md font-semibold text-[var(--ink)]">
              {citation.document_title}
            </h3>
          </div>

          {/* Details Grid */}
          <div className="grid grid-cols-2 gap-4 border-t border-b border-[var(--edge)] py-4">
            <div>
              <span className="text-[10px] font-bold uppercase tracking-wider text-[var(--ink-faint)]">
                Page
              </span>
              <p className="mt-1 text-sm font-semibold text-[var(--ink)]">
                {citation.page_number != null ? `Page ${citation.page_number}` : "—"}
              </p>
            </div>
            <div>
              <span className="text-[10px] font-bold uppercase tracking-wider text-[var(--ink-faint)]">
                Section
              </span>
              <p className="mt-1 text-sm font-semibold text-[var(--ink)] truncate" title={citation.section ?? undefined}>
                {citation.section ?? "—"}
              </p>
            </div>
          </div>

          {/* Relevance Card */}
          {citation.relevance_score != null && (
            <div className="rounded-[var(--radius-md)] border border-[var(--primary-muted)] bg-[var(--primary-faint)]/40 p-4">
              <div className="flex items-center gap-2 text-[var(--primary)]">
                <BarChart2 className="h-4 w-4" aria-hidden />
                <span className="text-xs font-bold uppercase tracking-wider">
                  Retrieval Score
                </span>
              </div>
              <p className="mt-2 text-2xl font-semibold text-[var(--ink)]" style={{ fontFamily: "var(--font-display)" }}>
                {Math.round(citation.relevance_score * 100)}%
                <span className="text-xs font-normal text-[var(--ink-muted)] ml-1.5">
                  match relevance
                </span>
              </p>
            </div>
          )}

          {/* Chunk Meta */}
          {citation.chunk_id && (
            <div className="space-y-1">
              <div className="flex items-center gap-1.5 text-[var(--ink-faint)]">
                <Shield className="h-3.5 w-3.5" aria-hidden />
                <span className="text-[9px] font-bold uppercase tracking-wider">
                  Verification ID
                </span>
              </div>
              <code className="block rounded bg-[var(--canvas-inset)] px-2 py-1 text-[10px] font-mono text-[var(--ink-muted)] break-all select-all">
                {citation.chunk_id}
              </code>
            </div>
          )}

          {/* Informational Hint */}
          <div className="text-[11px] text-[var(--ink-ghost)] leading-relaxed border-t border-[var(--edge)] pt-4">
            Answers are strictly grounded in this segment. The document contents have been processed into semantic chunks for verification.
          </div>
        </div>
      </div>
    </>
  );
}
