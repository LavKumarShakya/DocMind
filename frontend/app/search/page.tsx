"use client";

import { useState } from "react";
import { Loader2, Search, SearchX } from "lucide-react";

import { RequireAuth } from "@/components/require-auth";
import { SiteHeader } from "@/components/site-header";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ApiError } from "@/lib/api";
import { type UserSearchResult, userSearch } from "@/lib/chat";

function SearchPageShell() {
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
    <div className="min-h-screen bg-[var(--canvas)] text-[var(--ink)]">
      <SiteHeader />

      <main className="mx-auto max-w-5xl space-y-8 px-5 py-10 sm:px-8 animate-page-in">
        {/* Header */}
        <section>
          <h1
            className="text-3xl tracking-tight"
            style={{ fontFamily: "var(--font-display)" }}
          >
            Search documents
          </h1>
          <p className="mt-1.5 text-[var(--ink-faint)] max-w-lg">
            Find passages across the documents you can view. Search is grounded,
            permission-aware and never calls an LLM.
          </p>
        </section>

        {/* Search bar */}
        <form onSubmit={handleSearch} className="flex items-center gap-3">
          <div className="relative flex-1">
            <Search
              className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-[var(--ink-ghost)]"
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
          <Button
            type="submit"
            variant="accent"
            disabled={!query.trim() || searching}
          >
            {searching ? (
              <Loader2
                className="h-4 w-4"
                style={{ animation: "spin 0.7s linear infinite" }}
                aria-hidden
              />
            ) : (
              <Search className="h-4 w-4" aria-hidden />
            )}
            Search
          </Button>
        </form>

        {/* Error */}
        {error && <Alert variant="error">{error}</Alert>}

        {/* Empty state */}
        {results !== null && results.length === 0 && (
          <div className="flex flex-col items-center gap-3 rounded-[var(--radius-lg)] border-2 border-dashed border-[var(--edge-strong)] bg-[var(--canvas-raised)] p-12 text-center">
            <SearchX className="h-8 w-8 text-[var(--ink-ghost)]" aria-hidden />
            <p
              className="text-lg text-[var(--ink-faint)]"
              style={{ fontFamily: "var(--font-display)" }}
            >
              No results found.
            </p>
            <p className="text-sm text-[var(--ink-ghost)]">
              Try different keywords or check the documents you can view.
            </p>
          </div>
        )}

        {/* Results */}
        {results && results.length > 0 && (
          <section>
            <p className="text-sm text-[var(--ink-faint)]">
              {results.length} result{results.length === 1 ? "" : "s"} for{" "}
              <span className="font-semibold text-[var(--ink)]">
                &ldquo;{query}&rdquo;
              </span>
            </p>
            <ul className="mt-4 space-y-3">
              {results.map((result, i) => (
                <li
                  key={`${result.document_title}-${result.page_number}-${i}`}
                  className="rounded-[var(--radius-lg)] border border-[var(--edge)] bg-[var(--canvas-raised)] p-5 shadow-[var(--shadow-sm)] border-l-[3px] border-l-[var(--accent-muted)]"
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <h3 className="font-semibold text-[var(--ink)]">
                        {result.document_title}
                      </h3>
                      <p className="mt-0.5 text-xs text-[var(--ink-ghost)]">
                        {result.section ??
                          `Page ${result.page_number ?? "—"}`}
                      </p>
                    </div>
                    <span className="shrink-0 rounded-full bg-[var(--accent-faint)] border border-[var(--accent-muted)] px-2.5 py-0.5 text-xs font-semibold text-[var(--accent-hover)]">
                      {Math.round(result.relevance_score * 100)}% match
                    </span>
                  </div>
                  <p className="mt-3 text-sm leading-relaxed text-[var(--ink-muted)]">
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