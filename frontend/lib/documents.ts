/**
 * Document API client + types for the CampusRAG dashboard.
 */

import { apiDelete, apiGet, apiPatch, apiPost, apiUpload } from "@/lib/api";

export type DocumentStatus =
  | "UPLOADED"
  | "PROCESSING"
  | "ACTIVE"
  | "ARCHIVED"
  | "FAILED";

export type AccessLevel = "PUBLIC" | "STUDENT" | "FACULTY" | "ADMIN";

export interface CampusDocument {
  id: string;
  title: string;
  description: string | null;
  department: string | null;
  category: string | null;
  version: string;
  effective_date: string | null;
  status: DocumentStatus;
  access_level: AccessLevel;
  original_filename: string;
  mime_type: string;
  file_size: number;
  page_count: number | null;
  uploader_name: string | null;
  chunk_count: number | null;
  created_at: string;
  updated_at: string;
  processed_at: string | null;
  current_version_id: string | null;
}

export interface DocumentVersion {
  id: string;
  document_id: string;
  version_number: number;
  status: DocumentStatus;
  filename: string;
  file_size: number;
  page_count: number | null;
  created_at: string;
  processed_at: string | null;
}

export function uploadDocument(formData: FormData): Promise<CampusDocument> {
  return apiUpload<CampusDocument>("/api/documents", formData);
}

export function listDocuments(): Promise<CampusDocument[]> {
  return apiGet<CampusDocument[]>("/api/documents");
}

export function getDocument(id: string): Promise<CampusDocument> {
  return apiGet<CampusDocument>(`/api/documents/${id}`);
}

export function processDocument(id: string): Promise<CampusDocument> {
  return apiPost<CampusDocument>(`/api/documents/${id}/process`);
}

export function listVersions(id: string): Promise<DocumentVersion[]> {
  return apiGet<DocumentVersion[]>(`/api/documents/${id}/versions`);
}

export function uploadVersion(id: string, file: File): Promise<DocumentVersion> {
  const formData = new FormData();
  formData.append("file", file);
  return apiUpload<DocumentVersion>(`/api/documents/${id}/versions`, formData);
}

export function deleteDocument(id: string): Promise<{ status: string }> {
  return apiDelete<{ status: string }>(`/api/documents/${id}`);
}

export function updateDocument(
  id: string,
  body: Partial<Pick<CampusDocument, "title" | "access_level">>,
): Promise<CampusDocument> {
  return apiPatch<CampusDocument>(`/api/documents/${id}`, body);
}

/** Human-readable file size */
export function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export function formatDate(value: string | null): string {
  if (!value) return "—";
  return new Date(value).toLocaleDateString();
}