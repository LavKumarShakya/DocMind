"use client";

import { useState, useRef, useEffect } from "react";
import { Upload, X, File, AlertCircle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useToast } from "@/components/common/toast";
import { uploadDocument } from "@/lib/documents";
import { ApiError } from "@/lib/api";

interface UploadDialogProps {
  open: boolean;
  onClose: () => void;
  onSuccess: () => void;
}

export function UploadDialog({ open, onClose, onSuccess }: UploadDialogProps) {
  const { toast } = useToast();
  const dialogRef = useRef<HTMLDialogElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [dragActive, setDragActive] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const [title, setTitle] = useState("");
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const dialog = dialogRef.current;
    if (!dialog) return;
    if (open && !dialog.open) {
      dialog.showModal();
    } else if (!open && dialog.open) {
      dialog.close();
    }
  }, [open]);

  if (!open) return null;

  const handleDrag = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === "dragenter" || e.type === "dragover") {
      setDragActive(true);
    } else if (e.type === "dragleave") {
      setDragActive(false);
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);

    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      const droppedFile = e.dataTransfer.files[0];
      if (droppedFile.type === "application/pdf") {
        setFile(droppedFile);
        setError(null);
      } else {
        setError("Only PDF documents are supported.");
      }
    }
  };

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    e.preventDefault();
    if (e.target.files && e.target.files[0]) {
      setFile(e.target.files[0]);
      setError(null);
    }
  };

  const handleUploadSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!file) return;
    setUploading(true);
    setError(null);

    const formData = new FormData();
    formData.append("file", file);
    if (title.trim()) {
      formData.append("title", title.trim());
    }

    try {
      await uploadDocument(formData);
      toast("Document uploaded successfully.", "success");
      onSuccess();
      handleClose();
    } catch (err) {
      setError(
        err instanceof ApiError
          ? err.message
          : "Upload failed. Is the file a valid PDF?"
      );
      toast("Upload failed.", "error");
    } finally {
      setUploading(false);
    }
  };

  const handleClose = () => {
    setFile(null);
    setTitle("");
    setError(null);
    setUploading(false);
    onClose();
  };

  return (
    <dialog
      ref={dialogRef}
      onClose={handleClose}
      className="fixed inset-0 z-50 m-auto w-full max-w-md rounded-[var(--radius-lg)] border border-[var(--edge)] bg-[var(--canvas-raised)] p-0 shadow-[var(--shadow-lg)] backdrop:bg-[var(--ink)]/30 animate-page-in"
    >
      <div className="p-6">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-[var(--edge)] pb-3 mb-4">
          <h2 className="text-md font-semibold text-[var(--ink)]" style={{ fontFamily: "var(--font-display)" }}>
            Upload PDF
          </h2>
          <button
            type="button"
            onClick={handleClose}
            className="rounded-[var(--radius-sm)] p-1 text-[var(--ink-ghost)] hover:bg-[var(--canvas-inset)] hover:text-[var(--ink)]"
            aria-label="Close"
          >
            <X className="h-4 w-4" aria-hidden />
          </button>
        </div>

        {/* Form */}
        <form onSubmit={handleUploadSubmit} className="space-y-4">
          {error && (
            <div className="flex items-start gap-2 rounded-[var(--radius-sm)] border-l-[3px] border-l-[var(--danger)] bg-[var(--danger-faint)] p-3 text-xs text-[var(--danger)]">
              <AlertCircle className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden />
              <span>{error}</span>
            </div>
          )}

          {/* Drag and Drop Zone */}
          <div
            onDragEnter={handleDrag}
            onDragOver={handleDrag}
            onDragLeave={handleDrag}
            onDrop={handleDrop}
            onClick={() => fileInputRef.current?.click()}
            className={`flex flex-col items-center justify-center rounded-[var(--radius-md)] border-2 border-dashed p-8 text-center cursor-pointer transition-all ${
              dragActive
                ? "border-[var(--primary)] bg-[var(--primary-faint)]/50"
                : "border-[var(--edge-strong)] hover:border-[var(--primary-muted)] hover:bg-[var(--primary-faint)]/20"
            }`}
          >
            <input
              ref={fileInputRef}
              type="file"
              accept=".pdf,application/pdf"
              onChange={handleChange}
              className="hidden"
              disabled={uploading}
            />

            {file ? (
              <div className="space-y-2">
                <File className="h-8 w-8 text-[var(--primary)] mx-auto animate-bounce" aria-hidden />
                <p className="text-xs font-semibold text-[var(--ink)] line-clamp-1">
                  {file.name}
                </p>
                <span className="text-[10px] text-[var(--ink-faint)] block">
                  {(file.size / (1024 * 1024)).toFixed(2)} MB
                </span>
              </div>
            ) : (
              <div className="space-y-2">
                <Upload className="h-8 w-8 text-[var(--ink-ghost)] mx-auto" aria-hidden />
                <p className="text-xs text-[var(--ink-muted)]">
                  Drag and drop a PDF file here, or click to browse
                </p>
                <span className="text-[9px] text-[var(--ink-ghost)] block">
                  Max file size: 20 MB
                </span>
              </div>
            )}
          </div>

          {/* Optional Title Input */}
          <div className="space-y-1.5">
            <label htmlFor="upload-title" className="text-xs font-semibold text-[var(--ink-muted)]">
              Document Title (optional)
            </label>
            <Input
              id="upload-title"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="e.g. Academic Regulations 2026"
              disabled={uploading}
            />
          </div>

          {/* Actions */}
          <div className="flex items-center justify-end gap-3 pt-2">
            <button
              type="button"
              onClick={handleClose}
              className="rounded-[var(--radius-sm)] px-4 py-2 text-xs font-medium text-[var(--ink-muted)] hover:bg-[var(--canvas-inset)]"
              disabled={uploading}
            >
              Cancel
            </button>
            <Button
              type="submit"
              variant="primary"
              disabled={!file || uploading}
              className="text-xs h-9"
            >
              {uploading ? "Uploading…" : "Upload"}
            </Button>
          </div>
        </form>
      </div>
    </dialog>
  );
}
