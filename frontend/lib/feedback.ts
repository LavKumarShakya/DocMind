/**
 * Feedback API client + types for the DocMind dashboard.
 */

import { apiPost } from "@/lib/api";

export interface FeedbackRequest {
  message_id: string;
  rating: number;
  reason?: string;
}

export interface FeedbackResponse {
  id: string;
  message_id: string;
  rating: number;
  reason: string | null;
  created_at: string;
}

/** Submit or update feedback (one per user + message, upserted server-side). */
export function submitFeedback(body: FeedbackRequest): Promise<FeedbackResponse> {
  return apiPost<FeedbackResponse>("/api/feedback", body);
}
