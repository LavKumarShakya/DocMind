"use client";

import { createContext, useCallback, useContext, useState } from "react";
import { CheckCircle2, XCircle, Info, X } from "lucide-react";

import { cn } from "@/lib/utils";

type ToastVariant = "success" | "error" | "info";

interface Toast {
  id: string;
  message: string;
  variant: ToastVariant;
}

interface ToastContextValue {
  toast: (message: string, variant?: ToastVariant) => void;
}

const ToastContext = createContext<ToastContextValue | undefined>(undefined);

export function useToast(): ToastContextValue {
  const ctx = useContext(ToastContext);
  if (!ctx) throw new Error("useToast must be used within a ToastProvider");
  return ctx;
}

const icons: Record<ToastVariant, React.ReactNode> = {
  success: <CheckCircle2 className="h-4 w-4 text-[var(--success)]" aria-hidden />,
  error: <XCircle className="h-4 w-4 text-[var(--danger)]" aria-hidden />,
  info: <Info className="h-4 w-4 text-[var(--primary)]" aria-hidden />,
};

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);

  const toast = useCallback((message: string, variant: ToastVariant = "info") => {
    const id = `toast-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`;
    setToasts((current) => [...current, { id, message, variant }]);
    // Auto-dismiss after 4 seconds
    setTimeout(() => {
      setToasts((current) => current.filter((t) => t.id !== id));
    }, 4000);
  }, []);

  const dismiss = useCallback((id: string) => {
    setToasts((current) => current.filter((t) => t.id !== id));
  }, []);

  return (
    <ToastContext.Provider value={{ toast }}>
      {children}
      {/* Toast container */}
      <div className="toast-container" aria-live="polite">
        {toasts.map((t) => (
          <div
            key={t.id}
            className={cn(
              "flex items-center gap-2.5 rounded-[var(--radius-md)] border bg-[var(--canvas-raised)] px-4 py-3 text-sm shadow-[var(--shadow-lg)]",
              t.variant === "success" && "border-[var(--success)]/30",
              t.variant === "error" && "border-[var(--danger)]/30",
              t.variant === "info" && "border-[var(--primary)]/30",
            )}
            style={{ animation: "fade-in 0.25s ease-out" }}
            role="alert"
          >
            {icons[t.variant]}
            <span className="flex-1 text-[var(--ink)]">{t.message}</span>
            <button
              type="button"
              onClick={() => dismiss(t.id)}
              className="text-[var(--ink-ghost)] hover:text-[var(--ink-faint)] transition-colors"
              aria-label="Dismiss"
            >
              <X className="h-3.5 w-3.5" aria-hidden />
            </button>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}
