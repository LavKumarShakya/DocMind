import { type DocumentStatus } from "@/lib/documents";
import { cn } from "@/lib/utils";

const statusColors: Record<DocumentStatus, string> = {
  UPLOADED: "border-[var(--info)] bg-[var(--info-faint)] text-[var(--info)]",
  PROCESSING: "border-[var(--primary)] bg-[var(--primary-faint)] text-[var(--primary)]",
  ACTIVE: "border-[var(--success)] bg-[var(--success-faint)] text-[var(--success)]",
  FAILED: "border-[var(--danger)] bg-[var(--danger-faint)] text-[var(--danger)]",
  ARCHIVED: "border-[var(--edge-strong)] bg-[var(--canvas-inset)] text-[var(--ink-faint)]",
};

export function DocumentStatusBadge({ status }: { status: DocumentStatus }) {
  const displayLabel = status === "PROCESSING" 
    ? "Processing" 
    : status.charAt(0) + status.slice(1).toLowerCase();

  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full border px-2.5 py-0.5 text-[10px] font-bold uppercase tracking-wider",
        statusColors[status]
      )}
    >
      {displayLabel}
    </span>
  );
}
