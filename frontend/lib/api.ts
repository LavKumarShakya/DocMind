/**
 * API client for the CampusRAG backend.
 *
 * `NEXT_PUBLIC_API_URL` is baked in at build time and is safe to expose to the
 * browser — it is just the base URL of the public API and contains no secrets.
 *
 * The client automatically attaches the stored JWT (see `lib/auth.tsx`) to
 * every request and clears it when the backend answers with 401.
 */

const TOKEN_KEY = "campusrag_token";

export const API_URL =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    public readonly code: string,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

/** Token persistence helpers (localStorage; never store passwords). */
export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string): void {
  if (typeof window !== "undefined") {
    window.localStorage.setItem(TOKEN_KEY, token);
  }
}

export function clearToken(): void {
  if (typeof window !== "undefined") {
    window.localStorage.removeItem(TOKEN_KEY);
  }
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  const token = getToken();
  if (token) headers.set("Authorization", `Bearer ${token}`);
  if (!headers.has("Accept")) headers.set("Accept", "application/json");

  const res = await fetch(`${API_URL}${path}`, { ...init, headers });

  if (!res.ok) {
    if (res.status === 401) clearToken();
    let code = "HTTP_ERROR";
    let message = `Request failed with status ${res.status}`;
    try {
      const body = await res.json();
      if (body?.error) {
        code = body.error.code ?? code;
        message = body.error.message ?? message;
      }
    } catch {
      // response had no JSON body; keep the defaults
    }
    throw new ApiError(res.status, code, message);
  }

  return (await res.json()) as T;
}

export function apiGet<T>(path: string): Promise<T> {
  return request<T>(path, { method: "GET" });
}

export function apiPost<T>(
  path: string,
  body?: unknown,
  contentType: "json" | "form" = "json",
): Promise<T> {
  const init: RequestInit = { method: "POST" };
  if (body !== undefined) {
    if (contentType === "form") {
      init.headers = { "Content-Type": "application/x-www-form-urlencoded" };
      init.body = body as BodyInit;
    } else {
      init.headers = { "Content-Type": "application/json" };
      init.body = JSON.stringify(body);
    }
  }
  return request<T>(path, init);
}

export function apiPatch<T>(path: string, body?: unknown): Promise<T> {
  const init: RequestInit = { method: "PATCH" };
  if (body !== undefined) {
    init.headers = { "Content-Type": "application/json" };
    init.body = JSON.stringify(body);
  }
  return request<T>(path, init);
}

export function apiDelete<T>(path: string): Promise<T> {
  return request<T>(path, { method: "DELETE" });
}
