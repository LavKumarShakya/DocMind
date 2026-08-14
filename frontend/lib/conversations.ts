/**
 * Conversation API client + types for the CampusRAG dashboard.
 */

import { apiDelete, apiGet, apiPost } from "@/lib/api";

export type MessageRole = "USER" | "ASSISTANT";

export interface CitationDetail {
  chunk_id: string | null;
  document_id: string | null;
  document_title: string | null;
  page_number: number | null;
  section: string | null;
  relevance_score: number | null;
}

export interface MessageDetail {
  id: string;
  role: MessageRole;
  content: string;
  created_at: string;
  citations: CitationDetail[];
}

export interface ConversationSummary {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
}

export interface ConversationDetail extends ConversationSummary {
  messages: MessageDetail[];
}

export function listConversations(): Promise<ConversationSummary[]> {
  return apiGet<ConversationSummary[]>("/api/conversations");
}

export function getConversation(id: string): Promise<ConversationDetail> {
  return apiGet<ConversationDetail>(`/api/conversations/${id}`);
}

export function createConversation(title?: string): Promise<ConversationDetail> {
  return apiPost<ConversationDetail>("/api/conversations", { title });
}

export function deleteConversation(id: string): Promise<{ status: string }> {
  return apiDelete<{ status: string }>(`/api/conversations/${id}`);
}
