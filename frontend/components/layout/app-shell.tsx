"use client";

import { useState, useCallback } from "react";

import { Sidebar } from "@/components/layout/sidebar";
import { Topbar } from "@/components/layout/topbar";

/**
 * Shared application shell for all authenticated pages.
 * Provides persistent sidebar, topbar, and responsive mobile drawer.
 */
export function AppShell({ children }: { children: React.ReactNode }) {
  const [collapsed, setCollapsed] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);

  const toggleCollapse = useCallback(() => setCollapsed((c) => !c), []);
  const toggleMobile = useCallback(() => setMobileOpen((o) => !o), []);
  const closeMobile = useCallback(() => setMobileOpen(false), []);

  return (
    <div className="flex h-screen overflow-hidden bg-[var(--canvas)]">
      {/* Desktop sidebar */}
      <div className="hidden lg:block">
        <Sidebar collapsed={collapsed} onToggle={toggleCollapse} />
      </div>

      {/* Mobile sidebar overlay */}
      {mobileOpen && (
        <>
          {/* Backdrop */}
          <div
            className="fixed inset-0 z-40 bg-[var(--ink)]/30 lg:hidden"
            style={{ animation: "overlay-fade-in 0.2s ease-out" }}
            onClick={closeMobile}
            aria-hidden
          />
          {/* Drawer */}
          <div
            className="fixed inset-y-0 left-0 z-50 lg:hidden"
            style={{ animation: "slide-in-bottom 0.25s ease-out" }}
          >
            <Sidebar collapsed={false} onToggle={closeMobile} />
          </div>
        </>
      )}

      {/* Main area */}
      <div className="flex min-w-0 flex-1 flex-col">
        <Topbar onMenuClick={toggleMobile} />
        <main className="flex-1 overflow-y-auto">
          {children}
        </main>
      </div>
    </div>
  );
}
