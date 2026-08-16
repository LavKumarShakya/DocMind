"use client";

import { useEffect, useState, useCallback, useMemo } from "react";
import { FileText, Plus, Search, Loader2, RefreshCw } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { DocumentCard } from "@/components/documents/document-card";
import { UploadDialog } from "@/components/documents/upload-dialog";
import { ConfirmDialog } from "@/components/common/confirm-dialog";
import { EmptyState } from "@/components/common/empty-state";
import { listDocuments, deleteDocument, processDocument, type CampusDocument } from "@/lib/documents";
import { useToast } from "@/components/common/toast";

type FilterTab = "ALL" | "ACTIVE" | "PROCESSING" | "FAILED";

export default function DocumentsPage() {
  const { toast } = useToast();

  const [documents, setDocuments] = useState<CampusDocument[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState("");
  const [activeTab, setActiveTab] = useState<FilterTab>("ALL");

  const [uploadOpen, setUploadOpen] = useState(false);
  const [deleteId, setDeleteId] = useState<string | null>(null);
  const [deleteTitle, setDeleteTitle] = useState("");
  const [deletePending, setDeletePending] = useState(false);
  const [processingIds, setProcessingIds] = useState<Record<string, boolean>>({});

  const fetchDocuments = useCallback(async (silent = false) => {
    if (!silent) setLoading(true);
    try {
      const data = await listDocuments();
      setDocuments(data);
    } catch {
      toast("Unable to load document library.", "error");
    } finally {
      setLoading(false);
    }
  }, [toast]);

  useEffect(() => {
    void fetchDocuments();
  }, [fetchDocuments]);

  // Handle document processing
  const handleProcess = async (id: string) => {
    setProcessingIds((prev) => ({ ...prev, [id]: true }));
    try {
      await processDocument(id);
      toast("Processing initiated.", "success");
      await fetchDocuments(true);
    } catch {
      toast("Failed to initiate processing.", "error");
    } finally {
      setProcessingIds((prev) => ({ ...prev, [id]: false }));
    }
  };

  // Handle document deletion
  const handleDeleteClick = (id: string, title: string) => {
    setDeleteId(id);
    setDeleteTitle(title);
  };

  const handleConfirmDelete = async () => {
    if (!deleteId) return;
    setDeletePending(true);
    try {
      await deleteDocument(deleteId);
      toast("Document deleted successfully.", "success");
      await fetchDocuments(true);
    } catch {
      toast("Failed to delete document.", "error");
    } finally {
      setDeletePending(false);
      setDeleteId(null);
      setDeleteTitle("");
    }
  };

  // Local filtering & tab matching logic
  const filteredDocuments = useMemo(() => {
    return documents.filter((doc) => {
      const matchesSearch =
        doc.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
        doc.original_filename.toLowerCase().includes(searchQuery.toLowerCase());

      const matchesTab =
        activeTab === "ALL" || doc.status === activeTab;

      return matchesSearch && matchesTab;
    });
  }, [documents, searchQuery, activeTab]);

  if (loading) {
    return (
      <div className="mx-auto max-w-5xl px-6 py-10 space-y-8">
        <div className="flex justify-between items-center">
          <div className="h-8 w-32 skeleton" />
          <div className="h-10 w-28 skeleton" />
        </div>
        <div className="h-10 w-full skeleton" />
        <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
          {[1, 2, 3].map((n) => (
            <div key={n} className="h-44 skeleton" />
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-5xl px-4 py-8 sm:px-6 space-y-6 animate-page-in">
      {/* Title Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl tracking-tight text-[var(--ink)]" style={{ fontFamily: "var(--font-display)" }}>
            Documents
          </h1>
          <p className="text-xs text-[var(--ink-faint)]">
            Manage university regulations, ordinances, policies, and view status.
          </p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" size="sm" onClick={() => void fetchDocuments(true)}>
            <RefreshCw className="h-3.5 w-3.5" aria-hidden />
          </Button>
          <Button variant="primary" size="sm" onClick={() => setUploadOpen(true)}>
            <Plus className="h-4 w-4" aria-hidden />
            <span>Upload</span>
          </Button>
        </div>
      </div>

      {/* Search and Filters row */}
      <div className="flex flex-col sm:flex-row items-center gap-3">
        {/* Search */}
        <div className="relative flex-1 w-full">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-[var(--ink-ghost)]" aria-hidden />
          <Input
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search documents by title or filename…"
            className="pl-9"
          />
        </div>

        {/* Tab Filters */}
        <div className="flex rounded-[var(--radius-sm)] bg-[var(--canvas-inset)] p-1 shrink-0">
          {(["ALL", "ACTIVE", "PROCESSING", "FAILED"] as FilterTab[]).map((tab) => (
            <button
              key={tab}
              type="button"
              onClick={() => setActiveTab(tab)}
              className={`rounded-[var(--radius-sm)] px-3 py-1 text-xs font-semibold uppercase tracking-wider transition-all ${
                activeTab === tab
                  ? "bg-[var(--canvas-raised)] text-[var(--ink)] shadow-[var(--shadow-sm)]"
                  : "text-[var(--ink-faint)] hover:text-[var(--ink)]"
              }`}
            >
              {tab.toLowerCase()}
            </button>
          ))}
        </div>
      </div>

      {/* Grid List */}
      {filteredDocuments.length === 0 ? (
        <EmptyState
          icon={<FileText className="h-10 w-10" />}
          title="No documents found"
          description={
            searchQuery
              ? "No documents match your active search terms."
              : "Your document library is currently empty. Upload a PDF to begin."
          }
          action={
            !searchQuery && (
              <Button variant="outline" size="sm" onClick={() => setUploadOpen(true)}>
                Upload document
              </Button>
            )
          }
        />
      ) : (
        <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
          {filteredDocuments.map((doc) => (
            <DocumentCard
              key={doc.id}
              document={doc}
              onDelete={handleDeleteClick}
              onProcess={handleProcess}
              processing={processingIds[doc.id]}
            />
          ))}
        </div>
      )}

      {/* Modals */}
      <UploadDialog
        open={uploadOpen}
        onClose={() => setUploadOpen(false)}
        onSuccess={() => void fetchDocuments(true)}
      />

      <ConfirmDialog
        open={!!deleteId}
        title="Delete document?"
        description={`This will permanently remove the document "${deleteTitle}" and all of its associated semantic database chunks.`}
        confirmLabel="Delete"
        loading={deletePending}
        onConfirm={handleConfirmDelete}
        onCancel={() => {
          setDeleteId(null);
          setDeleteTitle("");
        }}
      />
    </div>
  );
}
export const dynamic = "force-dynamic";
