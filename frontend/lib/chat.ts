/**
 * Chat + search API client and types for the CampusRAG dashboard.
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

export function askQuestion(message: string): Promise<ChatResponse> {
  return apiPost<ChatResponse>("/api/chat", { message });
}

export function search(query: string): Promise<{ results: SearchResult[] }> {
  return apiPost<{ results: SearchResult[] }>("/api/search", { query });
}
