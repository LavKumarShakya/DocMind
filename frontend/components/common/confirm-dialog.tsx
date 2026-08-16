"use client";

import { useEffect, useRef } from "react";

import { cn } from "@/lib/utils";

/**
 * Confirmation dialog for destructive actions. Replaces window.confirm().
 */
export function ConfirmDialog({
  open,
  title,
  description,
  confirmLabel = "Confirm",
  cancelLabel = "Cancel",
  variant = "danger",
  loading = false,
  onConfirm,
  onCancel,
}: {
  open: boolean;
  title: string;
  description?: string;
  confirmLabel?: string;
  cancelLabel?: string;
  variant?: "danger" | "default";
  loading?: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}) {
  const dialogRef = useRef<HTMLDialogElement>(null);

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

  return (
    <dialog
      ref={dialogRef}
      className="fixed inset-0 z-50 m-auto w-full max-w-sm rounded-[var(--radius-lg)] border border-[var(--edge)] bg-[var(--canvas-raised)] p-0 shadow-[var(--shadow-lg)] backdrop:bg-[var(--ink)]/30 animate-page-in"
      onClose={onCancel}
      aria-labelledby="confirm-title"
    >
      <div className="p-6">
        <h2
          id="confirm-title"
          className="text-lg text-[var(--ink)]"
          style={{ fontFamily: "var(--font-display)" }}
        >
          {title}
        </h2>
        {description && (
          <p className="mt-2 text-sm text-[var(--ink-muted)] leading-relaxed">
            {description}
          </p>
        )}
        <div className="mt-6 flex items-center justify-end gap-3">
          <button
            type="button"
            onClick={onCancel}
            disabled={loading}
            className="rounded-[var(--radius-sm)] px-4 py-2 text-sm font-medium text-[var(--ink-muted)] hover:bg-[var(--canvas-inset)] transition-colors duration-150"
          >
            {cancelLabel}
          </button>
          <button
            type="button"
            onClick={onConfirm}
            disabled={loading}
            className={cn(
              "rounded-[var(--radius-sm)] px-4 py-2 text-sm font-semibold text-white shadow-[var(--shadow-sm)] transition-all duration-150 disabled:opacity-50",
              variant === "danger"
                ? "bg-[var(--danger)] hover:bg-[hsl(0,72%,44%)]"
                : "bg-[var(--ink)] hover:bg-[var(--ink-muted)]",
            )}
          >
            {loading ? "Processing…" : confirmLabel}
          </button>
        </div>
      </div>
    </dialog>
  );
}
