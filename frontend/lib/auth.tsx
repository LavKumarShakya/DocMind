"use client";

/**
 * Authentication state for the CampusRAG frontend.
 *
 * A single React context owns login / register / logout and restores the
 * current user from the persisted JWT on first load (via `/api/auth/me`).
 * Individual pages never touch the token directly.
 */

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
} from "react";

import { apiGet, apiPost, clearToken, getToken, setToken } from "@/lib/api";

export type Role = "STUDENT" | "FACULTY" | "ADMIN";

export interface User {
  id: string;
  email: string;
  name: string;
  role: Role;
  created_at: string;
}

interface TokenResponse {
  access_token: string;
  token_type: string;
  user: User;
}

type AuthStatus = "loading" | "authenticated" | "unauthenticated";

interface AuthContextValue {
  user: User | null;
  status: AuthStatus;
  login: (email: string, password: string) => Promise<void>;
  register: (name: string, email: string, password: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [status, setStatus] = useState<AuthStatus>("loading");

  // Restore the session from a persisted token.
  useEffect(() => {
    let cancelled = false;
    if (!getToken()) {
      setStatus("unauthenticated");
      return;
    }
    apiGet<User>("/api/auth/me")
      .then((currentUser) => {
        if (!cancelled) {
          setUser(currentUser);
          setStatus("authenticated");
        }
      })
      .catch(() => {
        if (!cancelled) {
          clearToken();
          setStatus("unauthenticated");
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const login = useCallback(async (email: string, password: string) => {
    const body = new URLSearchParams({ username: email, password });
    const res = await apiPost<TokenResponse>("/api/auth/login", body, "form");
    setToken(res.access_token);
    setUser(res.user);
    setStatus("authenticated");
  }, []);

  const register = useCallback(
    async (name: string, email: string, password: string) => {
      await apiPost<User>("/api/auth/register", { name, email, password });
    },
    [],
  );

  const logout = useCallback(() => {
    clearToken();
    setUser(null);
    setStatus("unauthenticated");
  }, []);

  return (
    <AuthContext.Provider value={{ user, status, login, register, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return ctx;
}
