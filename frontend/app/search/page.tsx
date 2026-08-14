"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { BookOpen, Loader2, Search, SearchX } from "lucide-react";

import { RequireAuth } from "@/components/require-auth";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { type UserSearchResult, userSearch } from "@/lib/chat";

function SearchPageShell() {
  const { user, logout } = useAuth();
  const router = useRouter();

  const [query, setQuery] = useState("");
  const [results, setResults] = useState<UserSearchResult[] | null>(null);
  const [searching, setSearching] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSearch(e: React.FormEvent) {
    e.preventDefault();
    const trimmed = query.trim();
    if (!trimmed || searching) return;
    setSearching(true);
    setError(null);
    setResults(null);
    try {
      const response = await userSearch(trimmed);
      setResults(response.results);
    } catch (err) {
      setError(
        err instanceof ApiError ? err.message : "Unable to run the search.",
      );
    } finally {
      setSearching(false);
    }
  }

  return (
    <div className="min-h-screen bg-zinc-50 text-zinc-900">
      <header className="border-b border-zinc-200 bg-white">
        <div className="mx-auto flex max-w-5xl items-center justify-between px-6 py-4">
          <div className="flex items-center gap-2 font-semibold">
            <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-indigo-600 text-white">
              <BookOpen className="h-4 w-4" aria-hidden />
            </span>
            CampusRAG
          </div>
          <nav className="hidden items-center gap-1 text-sm sm:flex">
            <Link
              href="/dashboard"
              className="rounded-lg px-3 py-1.5 text-zinc-600 hover:bg-zinc-100"
            >
              Dashboard
            </Link>
            <Link
              href="/search"
              className="rounded-lg px-3 py-1.5 font-medium text-indigo-600"
            >
              Search
            </Link>
            {user?.role === "ADMIN" && (
              <Link
                href="/admin"
                className="rounded-lg px-3 py-1.5 text-zinc-600 hover:bg-zinc-100"
              >
                Admin
              </Link>
            )}
          </nav>
          <div className="flex items-center gap-3">
            <span className="hidden text-sm text-zinc-600 sm:inline">
              {user?.email}
            </span>
            <Button variant="outline" size="sm" onClick={() => { logout(); router.push("/"); }}>
              Logout
            </Button>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-5xl space-y-6 px-6 py-10">
        <section>
          <h1 className="text-3xl font-semibold tracking-tight">Search documents</h1>
          <p className="mt-1 text-zinc-600">
            Find passages across the documents you can view. Search is grounded,
            permission-aware and never calls an LLM.
          </p>
        </section>

        <form onSubmit={handleSearch} className="flex items-center gap-3">
          <div className="relative flex-1">
            <Search
              className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-zinc-400"
              aria-hidden
            />
            <Input
              className="pl-9"
              placeholder="e.g. attendance policy"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              disabled={searching}
              maxLength={2000}
            />
          </div>
          <Button type="submit" disabled={!query.trim() || searching}>
            {searching ? (
              <Loader2 className="h-4 w-4 animate-spin" aria-hidden />
            ) : (
              <Search className="h-4 w-4" aria-hidden />
            )}
            Search
          </Button>
        </form>

        {error && <Alert variant="error">{error}</Alert>}

        {results !== null && results.length === 0 && (
          <div className="flex flex-col items-center gap-2 rounded-xl border border-dashed border-zinc-300 bg-white p-10 text-center">
            <SearchX className="h-6 w-6 text-zinc-400" aria-hidden />
            <p className="text-sm text-zinc-600">No results found.</p>
            <p className="text-xs text-zinc-400">
              Try different keywords or check the documents you can view.
            </p>
          </div>
        )}

        {results && results.length > 0 && (
          <section>
            <p className="text-sm text-zinc-500">
              {results.length} result{results.length === 1 ? "" : "s"} for{" "}
              <span className="font-medium text-zinc-700">"{query}"</span>
            </p>
            <ul className="mt-3 space-y-3">
              {results.map((result, i) => (
                <li
                  key={`${result.document_title}-${result.page_number}-${i}`}
                  className="rounded-xl border border-zinc-200 bg-white p-4 shadow-sm"
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <h3 className="font-medium text-zinc-900">
                        {result.document_title}
                      </h3>
                      <p className="mt-0.5 text-xs text-zinc-400">
                        {result.section ?? `Page ${result.page_number ?? "—"}`}
                      </p>
                    </div>
                    <span className="shrink-0 rounded-full bg-emerald-50 px-2 py-0.5 text-xs font-medium text-emerald-700">
                      {Math.round(result.relevance_score * 100)}% match
                    </span>
                  </div>
                  <p className="mt-2 text-sm leading-relaxed text-zinc-700">
                    {result.snippet}
                  </p>
                </li>
              ))}
            </ul>
          </section>
        )}
      </main>
    </div>
  );
}

export default function SearchPage() {
  return (
    <RequireAuth>
      <SearchPageShell />
    </RequireAuth>
  );
}