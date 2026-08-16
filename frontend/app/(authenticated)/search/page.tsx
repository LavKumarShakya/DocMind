"use client";

import { useState } from "react";
import { Search, Loader2, SearchX, HelpCircle, FileText } from "lucide-react";

import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { EmptyState } from "@/components/common/empty-state";
import { userSearch, type UserSearchResult } from "@/lib/chat";
import { useToast } from "@/components/common/toast";
import { ApiError } from "@/lib/api";

const SUGGESTED_TERMS = [
  "attendance requirement",
  "examination rules",
  "scholarship",
];

export default function SearchPage() {
  const { toast } = useToast();

  const [query, setQuery] = useState("");
  const [results, setResults] = useState<UserSearchResult[] | null>(null);
  const [searching, setSearching] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSearchSubmit = async (e: React.FormEvent) => {
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
        err instanceof ApiError ? err.message : "Unable to complete search query."
      );
      toast("Search query failed.", "error");
    } finally {
      setSearching(false);
    }
  };

  const handleSuggestedClick = (term: string) => {
    setQuery(term);
    // Submit query next loop cycle
    setTimeout(() => {
      const form = document.getElementById("search-form") as HTMLFormElement;
      if (form) {
        form.requestSubmit();
      }
    }, 50);
  };

  return (
    <div className="mx-auto max-w-4xl px-4 py-8 sm:px-6 space-y-8 animate-page-in">
      {/* Title Header */}
      <section>
        <h1 className="text-3xl tracking-tight text-[var(--ink)]" style={{ fontFamily: "var(--font-display)" }}>
          Search Documents
        </h1>
        <p className="text-xs text-[var(--ink-faint)]">
          Find matching passages and sections across all readable documents. No LLM calls.
        </p>
      </section>

      {/* Search Input Container */}
      <form id="search-form" onSubmit={handleSearchSubmit} className="flex gap-3">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-[var(--ink-ghost)]" aria-hidden />
          <Input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="e.g. attendance requirement"
            disabled={searching}
            className="pl-9"
          />
        </div>
        <Button type="submit" variant="primary" disabled={!query.trim() || searching}>
          {searching ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <Search className="h-4 w-4" />
          )}
          <span>Search</span>
        </Button>
      </form>

      {/* Suggested Search Chips */}
      {results === null && !searching && (
        <div className="flex flex-wrap items-center gap-2 pt-2">
          <span className="text-[10px] font-bold uppercase tracking-wider text-[var(--ink-ghost)] mr-1">
            Try searching for:
          </span>
          {SUGGESTED_TERMS.map((term) => (
            <button
              key={term}
              type="button"
              onClick={() => handleSuggestedClick(term)}
              className="rounded-full border border-[var(--edge-strong)] bg-[var(--canvas-raised)] px-3 py-1.5 text-xs text-[var(--ink-muted)] transition-all hover:border-[var(--primary-muted)] hover:bg-[var(--primary-faint)] hover:text-[var(--primary)]"
            >
              {term}
            </button>
          ))}
        </div>
      )}

      {/* Error Info */}
      {error && <Alert variant="error">{error}</Alert>}

      {/* Loading Skeletons */}
      {searching && (
        <div className="space-y-4">
          <div className="h-5 w-24 skeleton" />
          {[1, 2, 3].map((n) => (
            <div key={n} className="h-32 w-full skeleton" />
          ))}
        </div>
      )}

      {/* Results Empty state */}
      {results !== null && results.length === 0 && !searching && (
        <EmptyState
          icon={<SearchX className="h-10 w-10" />}
          title="No results found"
          description="Try different keywords, search phrases or adjust document search scope."
        />
      )}

      {/* Results List */}
      {results !== null && results.length > 0 && !searching && (
        <div className="space-y-4">
          <p className="text-xs text-[var(--ink-faint)] font-medium">
            Found {results.length} passage match{results.length === 1 ? "" : "es"} for{" "}
            <span className="font-semibold text-[var(--ink)]">&ldquo;{query}&rdquo;</span>
          </p>

          <ul className="space-y-4" role="list">
            {results.map((result, idx) => (
              <li
                key={idx}
                className="rounded-[var(--radius-lg)] border border-[var(--edge)] bg-[var(--canvas-raised)] p-5 shadow-[var(--shadow-sm)] border-l-4 border-l-[var(--primary-muted)] transition-all hover:border-[var(--edge-strong)] space-y-3"
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="flex items-center gap-2 min-w-0">
                    <FileText className="h-4 w-4 text-[var(--primary)] shrink-0" aria-hidden />
                    <h3 className="font-semibold text-sm text-[var(--ink)] truncate" style={{ fontFamily: "var(--font-display)" }}>
                      {result.document_title}
                    </h3>
                  </div>
                  <span className="rounded-full bg-[var(--primary-faint)] border border-[var(--primary-muted)] px-2.5 py-0.5 text-[10px] font-bold text-[var(--primary)] uppercase tracking-wide shrink-0">
                    {Math.round(result.relevance_score * 100)}% match
                  </span>
                </div>

                <p className="text-xs text-[var(--ink-faint)]">
                  {result.section ?? `Page ${result.page_number ?? "—"}`}
                </p>

                <p className="text-sm leading-relaxed text-[var(--ink-muted)] border-t border-[var(--edge)] pt-3 whitespace-pre-wrap">
                  {result.snippet}
                </p>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
export const dynamic = "force-dynamic";
