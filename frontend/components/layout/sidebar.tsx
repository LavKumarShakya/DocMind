"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  FileText,
  LayoutDashboard,
  MessageSquareText,
  Search,
  Settings,
  Shield,
  ChevronLeft,
  ChevronRight,
} from "lucide-react";

import { useAuth } from "@/lib/auth";
import { cn } from "@/lib/utils";

interface NavItem {
  href: string;
  label: string;
  icon: React.ReactNode;
}

export function Sidebar({
  collapsed,
  onToggle,
}: {
  collapsed: boolean;
  onToggle: () => void;
}) {
  const { user } = useAuth();
  const pathname = usePathname();

  const mainNav: NavItem[] = [
    {
      href: "/dashboard",
      label: "Dashboard",
      icon: <LayoutDashboard className="h-[18px] w-[18px]" aria-hidden />,
    },
    {
      href: "/chat",
      label: "Chat",
      icon: <MessageSquareText className="h-[18px] w-[18px]" aria-hidden />,
    },
    {
      href: "/documents",
      label: "Documents",
      icon: <FileText className="h-[18px] w-[18px]" aria-hidden />,
    },
    {
      href: "/search",
      label: "Search",
      icon: <Search className="h-[18px] w-[18px]" aria-hidden />,
    },
  ];

  const adminNav: NavItem[] =
    user?.role === "ADMIN"
      ? [
          {
            href: "/admin",
            label: "Admin",
            icon: <Shield className="h-[18px] w-[18px]" aria-hidden />,
          },
        ]
      : [];

  return (
    <aside
      className={cn(
        "flex h-full flex-col border-r border-[var(--edge)] bg-[var(--canvas-raised)] transition-[width] duration-200 ease-out",
        collapsed ? "w-16" : "w-64",
      )}
    >
      {/* Logo */}
      <div className="flex h-14 items-center gap-3 border-b border-[var(--edge)] px-4">
        <Link
          href="/dashboard"
          className="flex items-center gap-2.5 no-underline group"
        >
          <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-[var(--radius-sm)] bg-[var(--ink)] text-[var(--canvas)] text-sm font-bold">
            D
          </span>
          {!collapsed && (
            <span
              className="text-lg tracking-tight text-[var(--ink)] group-hover:text-[var(--primary)] transition-colors duration-150"
              style={{ fontFamily: "var(--font-display)" }}
            >
              DocMind
            </span>
          )}
        </Link>
      </div>

      {/* Navigation */}
      <nav className="flex-1 overflow-y-auto px-3 py-4" aria-label="Main">
        <ul className="space-y-1">
          {mainNav.map((item) => {
            const active =
              pathname === item.href || pathname.startsWith(item.href + "/");
            return (
              <li key={item.href}>
                <Link
                  href={item.href}
                  className={cn(
                    "flex items-center gap-3 rounded-[var(--radius-sm)] px-3 py-2 text-sm font-medium transition-all duration-150 no-underline",
                    active
                      ? "bg-[var(--primary-faint)] text-[var(--primary)] font-semibold"
                      : "text-[var(--ink-faint)] hover:bg-[var(--canvas-inset)] hover:text-[var(--ink)]",
                    collapsed && "justify-center px-2",
                  )}
                  title={collapsed ? item.label : undefined}
                >
                  {item.icon}
                  {!collapsed && <span>{item.label}</span>}
                </Link>
              </li>
            );
          })}
        </ul>

        {/* Admin separator */}
        {adminNav.length > 0 && (
          <>
            <div className="my-4 border-t border-[var(--edge)]" />
            <ul className="space-y-1">
              {adminNav.map((item) => {
                const active =
                  pathname === item.href ||
                  pathname.startsWith(item.href + "/");
                return (
                  <li key={item.href}>
                    <Link
                      href={item.href}
                      className={cn(
                        "flex items-center gap-3 rounded-[var(--radius-sm)] px-3 py-2 text-sm font-medium transition-all duration-150 no-underline",
                        active
                          ? "bg-[var(--primary-faint)] text-[var(--primary)] font-semibold"
                          : "text-[var(--ink-faint)] hover:bg-[var(--canvas-inset)] hover:text-[var(--ink)]",
                        collapsed && "justify-center px-2",
                      )}
                      title={collapsed ? item.label : undefined}
                    >
                      {item.icon}
                      {!collapsed && <span>{item.label}</span>}
                    </Link>
                  </li>
                );
              })}
            </ul>
          </>
        )}
      </nav>

      {/* Collapse toggle */}
      <div className="border-t border-[var(--edge)] px-3 py-3">
        <button
          type="button"
          onClick={onToggle}
          className={cn(
            "flex w-full items-center gap-3 rounded-[var(--radius-sm)] px-3 py-2 text-sm text-[var(--ink-ghost)] hover:bg-[var(--canvas-inset)] hover:text-[var(--ink-faint)] transition-colors duration-150",
            collapsed && "justify-center px-2",
          )}
          aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
        >
          {collapsed ? (
            <ChevronRight className="h-4 w-4" aria-hidden />
          ) : (
            <>
              <ChevronLeft className="h-4 w-4" aria-hidden />
              <span>Collapse</span>
            </>
          )}
        </button>
      </div>
    </aside>
  );
}
