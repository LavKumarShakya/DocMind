/**
 * Public demo mode API client and types.
 *
 * The demo endpoints require no authentication: they serve the unauthenticated
 * public demo page and answer questions exclusively from the single pre-indexed
 * demo document.
 */

import { apiGet, apiPost } from "@/lib/api";

export interface DemoInfo {
  demo_mode: boolean;
  document_id: string;
  document_title: string;
  /** "ready" when the pre-indexed demo document exists, else "missing". */
  status: "ready" | "missing";
  chunk_count: number | null;
}

export interface DemoCitation {
  chunk_id: string;
  document_id: string;
  document_title: string;
  page_number: number | null;
  section: string | null;
  chunk_index: number;
  relevance_score: number | null;
}

export interface DemoChatResponse {
  answer: string;
  citations: DemoCitation[];
  demo_mode: boolean;
}

export function getDemoInfo(): Promise<DemoInfo> {
  return apiGet<DemoInfo>("/api/demo/info");
}

export function askDemoQuestion(message: string): Promise<DemoChatResponse> {
  return apiPost<DemoChatResponse>("/api/demo/chat", { message });
}