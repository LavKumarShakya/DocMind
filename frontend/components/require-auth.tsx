"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

import { useAuth } from "@/lib/auth";

/**
 * Client-side route guard. Authorization is always enforced server-side;
 * this guard only improves the UX by redirecting unauthenticated users.
 */
export function RequireAuth({ children }: { children: React.ReactNode }) {
  const { status } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (status === "unauthenticated") {
      router.replace("/login");
    }
  }, [status, router]);

  if (status !== "authenticated") {
    return (
      <div className="flex min-h-screen items-center justify-center bg-[var(--canvas)]">
        <div className="flex flex-col items-center gap-3">
          <div
            className="h-8 w-8 rounded-full border-2 border-[var(--edge-strong)] border-t-[var(--accent)]"
            style={{ animation: "spin 0.7s linear infinite" }}
            aria-label="Loading"
          />
          <span
            className="text-sm text-[var(--ink-faint)]"
            style={{ animation: "pulse-soft 1.8s ease-in-out infinite" }}
          >
            Loading…
          </span>
        </div>
      </div>
    );
  }

  return <>{children}</>;
}
