"use client";

import { useRouter } from "next/navigation";
import { LogOut, Menu, Search, User as UserIcon, Shield } from "lucide-react";
import { useState, useRef, useEffect } from "react";

import { useAuth } from "@/lib/auth";
import { cn } from "@/lib/utils";

export function Topbar({ onMenuClick }: { onMenuClick: () => void }) {
  const { user, logout } = useAuth();
  const router = useRouter();
  const [menuOpen, setMenuOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setMenuOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  function handleLogout() {
    logout();
    router.push("/");
  }

  return (
    <header className="flex h-14 items-center justify-between gap-4 border-b border-[var(--edge)] bg-[var(--canvas-raised)] px-4 sm:px-6">
      {/* Mobile menu button */}
      <button
        type="button"
        onClick={onMenuClick}
        className="inline-flex h-9 w-9 items-center justify-center rounded-[var(--radius-sm)] text-[var(--ink-muted)] hover:bg-[var(--canvas-inset)] lg:hidden transition-colors duration-150"
        aria-label="Open navigation menu"
      >
        <Menu className="h-5 w-5" aria-hidden />
      </button>

      {/* Search trigger */}
      <button
        type="button"
        onClick={() => router.push("/search")}
        className="hidden items-center gap-2 rounded-[var(--radius-sm)] border border-[var(--edge)] bg-[var(--canvas)] px-3 py-1.5 text-sm text-[var(--ink-ghost)] hover:border-[var(--edge-strong)] hover:text-[var(--ink-faint)] transition-all duration-150 sm:flex"
      >
        <Search className="h-3.5 w-3.5" aria-hidden />
        <span>Search documents…</span>
        <kbd className="ml-8 rounded border border-[var(--edge)] bg-[var(--canvas-inset)] px-1.5 py-0.5 text-[10px] font-medium text-[var(--ink-ghost)]">
          ⌘K
        </kbd>
      </button>

      <div className="flex-1 sm:hidden" />

      {/* User menu */}
      <div className="relative" ref={menuRef}>
        <button
          type="button"
          onClick={() => setMenuOpen(!menuOpen)}
          className="flex items-center gap-2 rounded-[var(--radius-sm)] px-2 py-1.5 text-sm text-[var(--ink-muted)] hover:bg-[var(--canvas-inset)] transition-colors duration-150"
          aria-expanded={menuOpen}
          aria-label="User menu"
        >
          <span className="flex h-7 w-7 items-center justify-center rounded-full bg-[var(--primary-faint)] text-[var(--primary)] text-xs font-semibold">
            {user?.name?.charAt(0)?.toUpperCase() ?? "U"}
          </span>
          <span className="hidden text-[var(--ink)] font-medium sm:inline">
            {user?.name}
          </span>
        </button>

        {menuOpen && (
          <div className="absolute right-0 top-full mt-1 w-56 rounded-[var(--radius-md)] border border-[var(--edge)] bg-[var(--canvas-raised)] py-1 shadow-[var(--shadow-lg)] z-50 animate-page-in">
            {/* User info */}
            <div className="border-b border-[var(--edge)] px-3 py-2.5">
              <p className="text-sm font-semibold text-[var(--ink)]">
                {user?.name}
              </p>
              <p className="text-xs text-[var(--ink-faint)]">{user?.email}</p>
              <span className="mt-1 inline-flex items-center rounded-full border border-[var(--edge)] bg-[var(--canvas-inset)] px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-[var(--ink-faint)]">
                {user?.role}
              </span>
            </div>

            {/* Menu items */}
            {user?.role === "ADMIN" && (
              <button
                type="button"
                onClick={() => {
                  setMenuOpen(false);
                  router.push("/admin");
                }}
                className="flex w-full items-center gap-2.5 px-3 py-2 text-sm text-[var(--ink-muted)] hover:bg-[var(--canvas-inset)] hover:text-[var(--ink)] transition-colors duration-150"
              >
                <Shield className="h-4 w-4" aria-hidden />
                Admin
              </button>
            )}
            <button
              type="button"
              onClick={() => {
                setMenuOpen(false);
                handleLogout();
              }}
              className="flex w-full items-center gap-2.5 px-3 py-2 text-sm text-[var(--ink-muted)] hover:bg-[var(--canvas-inset)] hover:text-[var(--danger)] transition-colors duration-150"
            >
              <LogOut className="h-4 w-4" aria-hidden />
              Log out
            </button>
          </div>
        )}
      </div>
    </header>
  );
}
