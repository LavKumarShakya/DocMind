"use client";

import Link from "next/link";
import { FileText, Calendar, Database, Trash2, ArrowRight } from "lucide-react";
import { type CampusDocument, formatFileSize, formatDate } from "@/lib/documents";
import { DocumentStatusBadge } from "./document-status";
import { Button } from "@/components/ui/button";

interface DocumentCardProps {
  document: CampusDocument;
  onDelete: (id: string, title: string) => void;
  onProcess?: (id: string) => void;
  processing?: boolean;
}

export function DocumentCard({
  document: doc,
  onDelete,
  onProcess,
  processing = false,
}: DocumentCardProps) {
  const canProcess = (doc.status === "UPLOADED" || doc.status === "FAILED") && !processing;

  return (
    <div className="rounded-[var(--radius-lg)] border border-[var(--edge)] bg-[var(--canvas-raised)] p-5 shadow-[var(--shadow-sm)] border-l-4 border-l-[var(--primary-muted)] transition-all hover:border-[var(--edge-strong)] flex flex-col justify-between gap-4 animate-page-in">
      <div className="space-y-2">
        {/* Title + Status */}
        <div className="flex flex-wrap items-start justify-between gap-2">
          <Link href={`/documents/${doc.id}`} className="no-underline group">
            <h3 className="font-semibold text-sm text-[var(--ink)] group-hover:text-[var(--primary)] transition-colors line-clamp-1" style={{ fontFamily: "var(--font-display)" }}>
              {doc.title}
            </h3>
          </Link>
          <DocumentStatusBadge status={doc.status} />
        </div>

        {/* Details snippet */}
        <p className="text-xs text-[var(--ink-faint)] truncate" title={doc.original_filename}>
          {doc.original_filename}
        </p>

        {/* Info Grid */}
        <div className="grid grid-cols-2 gap-y-2 gap-x-4 pt-2 text-[11px] text-[var(--ink-muted)]">
          <div className="flex items-center gap-1.5 min-w-0">
            <FileText className="h-3.5 w-3.5 text-[var(--ink-ghost)] shrink-0" aria-hidden />
            <span className="truncate">
              {formatFileSize(doc.file_size)}
              {doc.page_count != null && ` · ${doc.page_count} pgs`}
            </span>
          </div>

          <div className="flex items-center gap-1.5 min-w-0">
            <Database className="h-3.5 w-3.5 text-[var(--ink-ghost)] shrink-0" aria-hidden />
            <span className="truncate">
              {doc.chunk_count != null && doc.chunk_count > 0 ? `${doc.chunk_count} chunks` : "no chunks"}
            </span>
          </div>

          <div className="flex items-center gap-1.5 min-w-0 col-span-2">
            <Calendar className="h-3.5 w-3.5 text-[var(--ink-ghost)] shrink-0" aria-hidden />
            <span className="truncate">
              Uploaded {formatDate(doc.created_at)}
            </span>
          </div>
        </div>
      </div>

      {/* Access Permission Tag */}
      <div className="flex items-center justify-between border-t border-[var(--edge)] pt-3 mt-1">
        <span className="rounded-full border border-[var(--edge)] bg-[var(--canvas-inset)] px-2 py-0.5 text-[9px] font-bold uppercase tracking-wider text-[var(--ink-faint)]">
          {doc.access_level === "PUBLIC" ? "Public" : `${doc.access_level.toLowerCase()} access`}
        </span>

        {/* Actions */}
        <div className="flex items-center gap-2">
          {canProcess && onProcess && (
            <Button
              size="sm"
              variant="primary"
              onClick={() => onProcess(doc.id)}
              className="h-7 text-[10px] px-2.5 font-bold tracking-wide uppercase"
            >
              Process
            </Button>
          )}
          {processing && (
            <span className="inline-flex items-center gap-1 text-[10px] font-semibold text-[var(--primary)] animate-pulse">
              Processing…
            </span>
          )}
          <Link href={`/documents/${doc.id}`}>
            <Button size="sm" variant="outline" className="h-7 px-2.5 text-[10px]">
              Detail
            </Button>
          </Link>
          <button
            type="button"
            onClick={() => onDelete(doc.id, doc.title)}
            disabled={processing}
            className="p-1 rounded text-[var(--ink-ghost)] hover:text-[var(--danger)] hover:bg-[var(--canvas-inset)] transition-all disabled:opacity-40"
            aria-label={`Delete document ${doc.title}`}
          >
            <Trash2 className="h-4 w-4" aria-hidden />
          </button>
        </div>
      </div>
    </div>
  );
}
export const dynamic = "force-dynamic";
