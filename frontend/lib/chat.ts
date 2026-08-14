/**
 * Chat + search API client and types for the DocMind dashboard.
 */

import { apiPost } from "@/lib/api";

export interface Citation {
  chunk_id: string;
  document_id: string;
  document_title: string;
  page_number: number | null;
  section: string | null;
  chunk_index: number;
  relevance_score: number | null;
}

export interface ChatResponse {
  answer: string;
  citations: Citation[];
  conversation_id: string;
  message_id: string;
}

export interface SearchResult {
  chunk_id: string;
  document_id: string;
  document_title: string;
  page_number: number | null;
  section: string | null;
  chunk_index: number;
  text: string;
  score: number | null;
  dense_score: number | null;
  bm25_score: number | null;
  hybrid_score: number | null;
  rerank_score: number | null;
}

/** Clean, user-facing search result (no raw scores or internal ids). */
export interface UserSearchResult {
  document_title: string;
  page_number: number | null;
  section: string | null;
  snippet: string;
  relevance_score: number;
}

export function askQuestion(
  message: string,
  conversationId?: string,
): Promise<ChatResponse> {
  return apiPost<ChatResponse>("/api/chat", {
    message,
    conversation_id: conversationId ?? null,
  });
}

export function search(query: string): Promise<{ results: SearchResult[] }> {
  return apiPost<{ results: SearchResult[] }>("/api/search", { query });
}

export function userSearch(query: string): Promise<{ results: UserSearchResult[] }> {
  return apiPost<{ results: UserSearchResult[] }>("/api/search/results", { query });
}
