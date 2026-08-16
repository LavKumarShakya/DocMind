"use client";

import { useEffect, useState, useCallback } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { ArrowLeft, Trash2, Calendar, FileText, Database, Shield, Settings, Info } from "lucide-react";

import { Button } from "@/components/ui/button";
import { DocumentStatusBadge } from "@/components/documents/document-status";
import { VersionTimeline } from "@/components/documents/version-timeline";
import { ConfirmDialog } from "@/components/common/confirm-dialog";
import { getDocument, deleteDocument, processDocument, type CampusDocument, formatFileSize, formatDate } from "@/lib/documents";
import { useToast } from "@/components/common/toast";
import { useAuth } from "@/lib/auth";

export default function DocumentDetailPage() {
  const params = useParams();
  const router = useRouter();
  const { toast } = useToast();
  const { user } = useAuth();
  const documentId = params?.id as string;

  const [document, setDocument] = useState<CampusDocument | null>(null);
  const [loading, setLoading] = useState(true);
  const [processing, setProcessing] = useState(false);
  const [deleteOpen, setDeleteOpen] = useState(false);
  const [deletePending, setDeletePending] = useState(false);

  const fetchDetails = useCallback(async (silent = false) => {
    if (!silent) setLoading(true);
    try {
      const data = await getDocument(documentId);
      setDocument(data);
    } catch {
      toast("Unable to load document details.", "error");
      router.push("/documents");
    } finally {
      setLoading(false);
    }
  }, [documentId, router, toast]);

  useEffect(() => {
    if (documentId) {
      void fetchDetails();
    }
  }, [documentId, fetchDetails]);

  const handleProcess = async () => {
    if (!document) return;
    setProcessing(true);
    try {
      await processDocument(document.id);
      toast("Processing initiated successfully.", "success");
      await fetchDetails(true);
    } catch {
      toast("Failed to initiate processing.", "error");
    } finally {
      setProcessing(false);
    }
  };

  const handleDelete = async () => {
    if (!document) return;
    setDeletePending(true);
    try {
      await deleteDocument(document.id);
      toast("Document deleted successfully.", "success");
      router.push("/documents");
    } catch {
      toast("Failed to delete document.", "error");
    } finally {
      setDeletePending(false);
      setDeleteOpen(false);
    }
  };

  if (loading) {
    return (
      <div className="mx-auto max-w-4xl px-6 py-10 space-y-8">
        <div className="h-6 w-24 skeleton" />
        <div className="h-10 w-64 skeleton" />
        <div className="grid gap-6 md:grid-cols-[1fr_250px]">
          <div className="h-64 skeleton" />
          <div className="h-64 skeleton" />
        </div>
      </div>
    );
  }

  if (!document) return null;

  const canProcess = document.status === "UPLOADED" || document.status === "FAILED";
  const showAdminActions = user?.role === "ADMIN" || user?.role === "FACULTY";

  return (
    <div className="mx-auto max-w-4xl px-4 py-8 sm:px-6 space-y-8 animate-page-in">
      {/* Back button */}
      <div>
        <Link href="/documents" className="inline-flex items-center gap-1 text-xs font-semibold text-[var(--ink-faint)] hover:text-[var(--primary)] transition-colors no-underline">
          <ArrowLeft className="h-3.5 w-3.5" aria-hidden />
          <span>Back to library</span>
        </Link>
      </div>

      {/* Header Info */}
      <div className="flex flex-wrap items-start justify-between gap-4 border-b border-[var(--edge)] pb-6">
        <div className="space-y-2 min-w-0">
          <div className="flex flex-wrap items-center gap-2.5">
            <h1 className="text-3xl tracking-tight text-[var(--ink)]" style={{ fontFamily: "var(--font-display)" }}>
              {document.title}
            </h1>
            <DocumentStatusBadge status={document.status} />
          </div>
          <p className="text-xs text-[var(--ink-faint)] select-all truncate">
            ID: {document.id}
          </p>
        </div>

        {/* Action buttons */}
        {showAdminActions && (
          <div className="flex items-center gap-2 shrink-0">
            {canProcess && (
              <Button onClick={handleProcess} disabled={processing} variant="primary" size="sm">
                {processing ? "Processing…" : "Process Document"}
              </Button>
            )}
            <Button onClick={() => setDeleteOpen(true)} variant="destructive" size="sm">
              <Trash2 className="h-3.5 w-3.5 mr-1" />
              Delete
            </Button>
          </div>
        )}
      </div>

      {/* Grid Layout */}
      <div className="grid gap-8 md:grid-cols-[1fr_320px]">
        {/* Left Column: Metadata & Details */}
        <div className="space-y-6">
          <div className="rounded-[var(--radius-lg)] border border-[var(--edge)] bg-[var(--canvas-raised)] p-6 shadow-[var(--shadow-sm)] space-y-4">
            <h3 className="text-md font-semibold border-b border-[var(--edge)] pb-2" style={{ fontFamily: "var(--font-display)" }}>
              Overview
            </h3>
            
            {/* Attributes Grid */}
            <dl className="grid grid-cols-2 gap-y-4 gap-x-6 text-xs">
              <div>
                <dt className="text-[var(--ink-faint)] font-medium">Original Filename</dt>
                <dd className="mt-1 font-semibold text-[var(--ink)] break-all select-all">{document.original_filename}</dd>
              </div>
              <div>
                <dt className="text-[var(--ink-faint)] font-medium">Access Permission</dt>
                <dd className="mt-1 font-semibold text-[var(--ink)]">{document.access_level}</dd>
              </div>
              <div>
                <dt className="text-[var(--ink-faint)] font-medium">File Size</dt>
                <dd className="mt-1 font-semibold text-[var(--ink)]">{formatFileSize(document.file_size)}</dd>
              </div>
              <div>
                <dt className="text-[var(--ink-faint)] font-medium">Page Count</dt>
                <dd className="mt-1 font-semibold text-[var(--ink)]">{document.page_count ?? "—"}</dd>
              </div>
              <div>
                <dt className="text-[var(--ink-faint)] font-medium">Chunks Extracted</dt>
                <dd className="mt-1 font-semibold text-[var(--ink)]">{document.chunk_count ?? "0"}</dd>
              </div>
              <div>
                <dt className="text-[var(--ink-faint)] font-medium">Current Version</dt>
                <dd className="mt-1 font-semibold text-[var(--ink)]">v{document.version}</dd>
              </div>
            </dl>
          </div>

          <div className="rounded-[var(--radius-lg)] border border-[var(--edge)] bg-[var(--canvas-raised)] p-6 shadow-[var(--shadow-sm)] space-y-4">
            <h3 className="text-md font-semibold border-b border-[var(--edge)] pb-2" style={{ fontFamily: "var(--font-display)" }}>
              Audit Info
            </h3>
            <dl className="grid grid-cols-2 gap-y-4 gap-x-6 text-xs">
              <div>
                <dt className="text-[var(--ink-faint)] font-medium">Uploader</dt>
                <dd className="mt-1 font-semibold text-[var(--ink)]">{document.uploader_name ?? "System"}</dd>
              </div>
              <div>
                <dt className="text-[var(--ink-faint)] font-medium">Category</dt>
                <dd className="mt-1 font-semibold text-[var(--ink)]">{document.category ?? "General"}</dd>
              </div>
              <div>
                <dt className="text-[var(--ink-faint)] font-medium">Created Date</dt>
                <dd className="mt-1 font-semibold text-[var(--ink)]">{formatDate(document.created_at)}</dd>
              </div>
              <div>
                <dt className="text-[var(--ink-faint)] font-medium">Processed Date</dt>
                <dd className="mt-1 font-semibold text-[var(--ink)]">{formatDate(document.processed_at)}</dd>
              </div>
            </dl>
          </div>
        </div>

        {/* Right Column: Versions Timeline */}
        <div>
          <div className="rounded-[var(--radius-lg)] border border-[var(--edge)] bg-[var(--canvas-raised)] p-6 shadow-[var(--shadow-sm)]">
            <VersionTimeline documentId={document.id} />
          </div>
        </div>
      </div>

      {/* Delete Confirmation */}
      <ConfirmDialog
        open={deleteOpen}
        title="Delete document?"
        description={`This will permanently remove "${document.title}" and all associated versions.`}
        confirmLabel="Delete"
        loading={deletePending}
        onConfirm={handleDelete}
        onCancel={() => setDeleteOpen(false)}
      />
    </div>
  );
}
export const dynamic = "force-dynamic";
