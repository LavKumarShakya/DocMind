import * as React from "react";

import { cn } from "@/lib/utils";

const Input = React.forwardRef<
  HTMLInputElement,
  React.InputHTMLAttributes<HTMLInputElement>
>(({ className, type, ...props }, ref) => (
  <input
    ref={ref}
    type={type}
    className={cn(
      "flex h-10 w-full rounded-[var(--radius-sm)] border border-[var(--edge-strong)] bg-[var(--canvas-raised)] px-3 py-2 text-sm text-[var(--ink)] placeholder:text-[var(--ink-ghost)] transition-colors duration-150 focus:border-[var(--primary)] focus:outline-none focus:ring-2 focus:ring-[var(--primary)]/25 disabled:cursor-not-allowed disabled:opacity-45",
      className,
    )}
    {...props}
  />
));
Input.displayName = "Input";

export { Input };
