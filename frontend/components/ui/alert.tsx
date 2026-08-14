import * as React from "react";

import { cn } from "@/lib/utils";

interface AlertProps extends React.HTMLAttributes<HTMLDivElement> {
  variant?: "error" | "success" | "info";
}

export function Alert({
  variant,
  className,
  ...props
}: AlertProps) {
  return (
    <div
      role="alert"
      className={cn(
        "rounded-[var(--radius-sm)] border-l-[3px] px-4 py-3 text-sm",
        variant === "error" &&
          "border-l-[var(--danger)] bg-[var(--danger-faint)] text-[var(--danger)]",
        variant === "success" &&
          "border-l-[var(--success)] bg-[var(--success-faint)] text-[var(--success)]",
        variant === "info" &&
          "border-l-[var(--info)] bg-[var(--info-faint)] text-[var(--info)]",
        !variant &&
          "border-l-[var(--edge-strong)] bg-[var(--canvas-inset)] text-[var(--ink-muted)]",
        className,
      )}
      {...props}
    />
  );
}
