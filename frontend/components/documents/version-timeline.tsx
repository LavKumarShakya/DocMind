"use client";

import { useEffect, useState, useRef, useCallback } from "react";
import { Upload, Loader2, Clock, CheckCircle2, AlertCircle } from "lucide-react";
import { listVersions, uploadVersion, type DocumentVersion, formatFileSize, formatDate } from "@/lib/documents";
import { DocumentStatusBadge } from "./document-status";
import { useToast } from "@/components/common/toast";
import { ApiError } from "@/lib/api";

interface VersionTimelineProps {
  documentId: string;
}

export function VersionTimeline({ documentId }: { documentId: string }) {
  const { toast } = useToast();
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [versions, setVersions] = useState<DocumentVersion[]>([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchVersions = useCallback(async () => {
    try {
      const list = await listVersions(documentId);
      // Sort descending by version number
      setVersions(list.sort((a, b) => b.version_number - a.version_number));
    } catch {
      toast("Unable to load version history.", "error");
    } finally {
      setLoading(false);
    }
  }, [documentId, toast]);

  useEffect(() => {
    void fetchVersions();
  }, [fetchVersions]);

  const handleUploadClick = () => {
    fileInputRef.current?.click();
  };

  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    if (file.type !== "application/pdf") {
      setError("Only PDF files are supported for new versions.");
      return;
    }

    setUploading(true);
    setError(null);
    try {
      await uploadVersion(documentId, file);
      toast("New version uploaded successfully.", "success");
      await fetchVersions();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Upload failed.");
      toast("Failed to upload new version.", "error");
    } finally {
      setUploading(false);
      if (fileInputRef.current) {
        fileInputRef.current.value = "";
      }
    }
  };

  if (loading) {
    return (
      <div className="flex items-center gap-2 py-4 text-xs text-[var(--ink-faint)]">
        <Loader2 className="h-4 w-4 text-[var(--primary)] animate-spin" aria-hidden />
        <span>Loading version timeline…</span>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-[var(--edge)] pb-3">
        <div className="flex items-center gap-2">
          <Clock className="h-4 w-4 text-[var(--primary)]" aria-hidden />
          <h4 className="text-sm font-semibold text-[var(--ink)]" style={{ fontFamily: "var(--font-display)" }}>
            Version Timeline
          </h4>
        </div>
        <button
          type="button"
          onClick={handleUploadClick}
          disabled={uploading}
          className="cursor-pointer text-xs font-semibold text-[var(--primary)] hover:text-[var(--primary-hover)] transition-colors disabled:opacity-40"
        >
          {uploading ? "Uploading…" : "Upload Version"}
        </button>
        <input
          ref={fileInputRef}
          type="file"
          accept=".pdf,application/pdf"
          onChange={handleFileChange}
          className="hidden"
          disabled={uploading}
        />
      </div>

      {error && (
        <div className="flex items-start gap-2 rounded-[var(--radius-sm)] border-l-[3px] border-l-[var(--danger)] bg-[var(--danger-faint)] p-3 text-xs text-[var(--danger)]">
          <AlertCircle className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden />
          <span>{error}</span>
        </div>
      )}

      {/* Timeline list */}
      {versions.length === 0 ? (
        <p className="text-xs text-[var(--ink-ghost)] py-4 text-center">
          No versions found.
        </p>
      ) : (
        <div className="relative pl-6 space-y-6 border-l border-[var(--edge-strong)] ml-3 pt-1">
          {versions.map((version, idx) => {
            const isActive = version.status === "ACTIVE" || idx === 0;
            return (
              <div key={version.id} className="relative">
                {/* Timeline node dot */}
                <span
                  className={`absolute -left-[30px] top-1 flex h-4 w-4 items-center justify-center rounded-full border bg-[var(--canvas-raised)] ${
                    isActive
                      ? "border-[var(--primary)] text-[var(--primary)]"
                      : "border-[var(--edge-strong)] text-[var(--ink-ghost)]"
                  }`}
                >
                  <span className={`h-1.5 w-1.5 rounded-full ${isActive ? "bg-[var(--primary)]" : "bg-[var(--edge-strong)]"}`} />
                </span>

                <div className="flex flex-col gap-1 sm:flex-row sm:items-center sm:justify-between">
                  <div>
                    <h5 className="text-xs font-semibold text-[var(--ink)]">
                      Version {version.version_number}{" "}
                      <span className="font-normal text-[var(--ink-faint)]">
                        ({version.filename})
                      </span>
                    </h5>
                    <p className="text-[10px] text-[var(--ink-ghost)]">
                      Uploaded {formatDate(version.created_at)} · {formatFileSize(version.file_size)}
                      {version.page_count != null && ` · ${version.page_count} pages`}
                    </p>
                  </div>
                  <div className="mt-1 sm:mt-0 shrink-0">
                    <DocumentStatusBadge status={version.status} />
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
