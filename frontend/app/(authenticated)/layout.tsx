"use client";

import { RequireAuth } from "@/components/require-auth";
import { AppShell } from "@/components/layout/app-shell";
import { ToastProvider } from "@/components/common/toast";

export default function AuthenticatedLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <RequireAuth>
      <ToastProvider>
        <AppShell>{children}</AppShell>
      </ToastProvider>
    </RequireAuth>
  );
}
