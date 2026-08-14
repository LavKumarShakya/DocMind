/**
 * Admin API client + types for the DocMind admin dashboard.
 */

import { apiGet, apiPatch } from "@/lib/api";
import type { AccessLevel, DocumentStatus } from "@/lib/documents";

export type Role = "STUDENT" | "FACULTY" | "ADMIN";

export interface AdminUser {
  id: string;
  name: string;
  email: string;
  role: Role;
  created_at: string;
}

export interface AdminDocument {
  id: string;
  title: string;
  owner_name: string | null;
  access_level: AccessLevel;
  status: DocumentStatus;
  version: string;
  current_version_id: string | null;
  page_count: number | null;
  chunk_count: number | null;
  created_at: string;
  updated_at: string;
}

export interface AdminStats {
  users: number;
  documents: number;
  active_documents: number;
  failed_documents: number;
  conversations: number;
  feedback_entries: number;
}

export function listAdminUsers(): Promise<AdminUser[]> {
  return apiGet<AdminUser[]>("/api/admin/users");
}

export function listAdminDocuments(): Promise<AdminDocument[]> {
  return apiGet<AdminDocument[]>("/api/admin/documents");
}

export function getAdminStats(): Promise<AdminStats> {
  return apiGet<AdminStats>("/api/admin/stats");
}

export function updateUserRole(id: string, role: Role): Promise<AdminUser> {
  return apiPatch<AdminUser>(`/api/admin/users/${id}/role`, { role });
}
