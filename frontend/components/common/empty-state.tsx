import { cn } from "@/lib/utils";

/**
 * Reusable empty state for pages with no content.
 */
export function EmptyState({
  icon,
  title,
  description,
  action,
  className,
}: {
  icon?: React.ReactNode;
  title: string;
  description?: string;
  action?: React.ReactNode;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "flex flex-col items-center gap-3 rounded-[var(--radius-lg)] border-2 border-dashed border-[var(--edge-strong)] bg-[var(--canvas-raised)] px-8 py-12 text-center",
        className,
      )}
    >
      {icon && (
        <div className="text-[var(--ink-ghost)]">{icon}</div>
      )}
      <h3
        className="text-lg text-[var(--ink-faint)]"
        style={{ fontFamily: "var(--font-display)" }}
      >
        {title}
      </h3>
      {description && (
        <p className="max-w-sm text-sm text-[var(--ink-ghost)]">{description}</p>
      )}
      {action && <div className="mt-2">{action}</div>}
    </div>
  );
}
