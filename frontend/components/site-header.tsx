"use client";

import { useState } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { Menu, X } from "lucide-react";

import { Button } from "@/components/ui/button";
import { useAuth } from "@/lib/auth";
import { cn } from "@/lib/utils";

/**
 * Shared editorial-style app header for authenticated pages.
 * Features a serif wordmark, underline-accented navigation, and
 * a mobile hamburger menu for small screens.
 */
export function SiteHeader() {
  const { user, logout } = useAuth();
  const router = useRouter();
  const pathname = usePathname();
  const [menuOpen, setMenuOpen] = useState(false);

  const navItems = [
    { href: "/dashboard", label: "Dashboard" },
    { href: "/search", label: "Search" },
    ...(user?.role === "ADMIN" ? [{ href: "/admin", label: "Admin" }] : []),
  ];

  function handleLogout() {
    logout();
    router.push("/");
  }

  return (
    <header className="border-b border-[var(--edge)] bg-[var(--canvas-raised)]">
      <div className="mx-auto flex max-w-7xl items-center justify-between gap-4 px-5 py-4 sm:px-8">
        {/* Wordmark */}
        <Link
          href="/dashboard"
          className="flex items-center gap-3 group no-underline"
        >
          <span className="flex h-9 w-9 items-center justify-center rounded-[var(--radius-sm)] bg-[var(--ink)] text-[var(--canvas)] font-bold text-sm tracking-tight">
            D
          </span>
          <span
            className="text-xl tracking-tight text-[var(--ink)] group-hover:text-[var(--accent)] transition-colors duration-150"
            style={{ fontFamily: "var(--font-display)" }}
          >
            DocMind
          </span>
        </Link>

        {/* Desktop navigation */}
        <nav className="hidden items-center gap-1 sm:flex" aria-label="Main">
          {navItems.map((item) => {
            const active = pathname === item.href;
            return (
              <Link
                key={item.href}
                href={item.href}
                className={cn(
                  "relative px-3 py-1.5 text-sm font-medium transition-colors duration-150 rounded-[var(--radius-sm)]",
                  active
                    ? "text-[var(--ink)]"
                    : "text-[var(--ink-faint)] hover:text-[var(--ink)] hover:bg-[var(--canvas-inset)]",
                )}
              >
                {item.label}
                {active && (
                  <span className="absolute bottom-0 left-3 right-3 h-[2px] rounded-full bg-[var(--accent)]" />
                )}
              </Link>
            );
          })}
        </nav>

        {/* Right side */}
        <div className="flex items-center gap-3">
          <span className="hidden text-sm text-[var(--ink-faint)] sm:inline">
            {user?.name}
          </span>
          <Button variant="ghost" size="sm" onClick={handleLogout}>
            Log out
          </Button>

          {/* Mobile menu toggle */}
          <button
            type="button"
            onClick={() => setMenuOpen((open) => !open)}
            aria-expanded={menuOpen}
            aria-label={menuOpen ? "Close navigation menu" : "Open navigation menu"}
            className="inline-flex h-9 w-9 items-center justify-center rounded-[var(--radius-sm)] border border-[var(--edge)] text-[var(--ink-muted)] hover:bg-[var(--canvas-inset)] sm:hidden transition-colors duration-150"
          >
            {menuOpen ? (
              <X className="h-4 w-4" aria-hidden />
            ) : (
              <Menu className="h-4 w-4" aria-hidden />
            )}
          </button>
        </div>
      </div>

      {/* Mobile nav */}
      {menuOpen && (
        <nav
          className="border-t border-[var(--edge)] px-5 py-3 sm:hidden"
          aria-label="Main mobile"
        >
          {navItems.map((item) => {
            const active = pathname === item.href;
            return (
              <Link
                key={item.href}
                href={item.href}
                onClick={() => setMenuOpen(false)}
                className={cn(
                  "block rounded-[var(--radius-sm)] px-3 py-2.5 text-sm font-medium transition-colors duration-150",
                  active
                    ? "text-[var(--ink)] bg-[var(--canvas-inset)]"
                    : "text-[var(--ink-faint)] hover:text-[var(--ink)] hover:bg-[var(--canvas-inset)]",
                )}
              >
                {item.label}
              </Link>
            );
          })}
        </nav>
      )}
    </header>
  );
}
