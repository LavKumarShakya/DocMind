"use client";

import { FormEvent, Suspense, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Loader2, Shield } from "lucide-react";

import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";

function LoginForm() {
  const { login, status } = useAuth();
  const router = useRouter();
  const searchParams = useSearchParams();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const justRegistered = searchParams.get("registered") === "1";

  useEffect(() => {
    if (status === "authenticated") {
      router.replace("/dashboard");
    }
  }, [status, router]);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await login(email, password);
      router.push("/dashboard");
    } catch (err) {
      setError(
        err instanceof ApiError
          ? err.message
          : "Unable to sign in. Please try again."
      );
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main className="flex min-h-screen items-center justify-center bg-[var(--canvas)] px-6 text-[var(--ink)]">
      <div className="w-full max-w-sm space-y-8 animate-page-in">
        {/* Logo Wordmark */}
        <div className="space-y-3 text-center">
          <span className="inline-flex h-12 w-12 items-center justify-center rounded-[var(--radius-md)] bg-[var(--ink)] text-[var(--canvas)] font-bold text-lg shadow-[var(--shadow-md)]">
            D
          </span>
          <h1
            className="text-3xl tracking-tight text-[var(--ink)]"
            style={{ fontFamily: "var(--font-display)" }}
          >
            Sign in to DocMind
          </h1>
          <p className="text-xs text-[var(--ink-faint)]">
            Enter your credentials to query university knowledge sources.
          </p>
        </div>

        {/* Card */}
        <form
          onSubmit={handleSubmit}
          className="space-y-5 rounded-[var(--radius-lg)] border border-[var(--edge)] bg-[var(--canvas-raised)] p-7 shadow-[var(--shadow-md)]"
        >
          {justRegistered && (
            <Alert variant="success">Account created. Please sign in.</Alert>
          )}
          {error && <Alert variant="error">{error}</Alert>}

          <div className="space-y-1.5">
            <label
              htmlFor="email"
              className="text-xs font-semibold text-[var(--ink-muted)]"
            >
              Email address
            </label>
            <Input
              id="email"
              type="email"
              required
              autoComplete="email"
              placeholder="you@university.edu"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              disabled={submitting}
            />
          </div>

          <div className="space-y-1.5">
            <label
              htmlFor="password"
              className="text-xs font-semibold text-[var(--ink-muted)]"
            >
              Password
            </label>
            <Input
              id="password"
              type="password"
              required
              autoComplete="current-password"
              placeholder="••••••••"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              disabled={submitting}
            />
          </div>

          <Button type="submit" variant="primary" className="w-full" disabled={submitting}>
            {submitting && (
              <Loader2
                className="h-4 w-4"
                style={{ animation: "spin 0.7s linear infinite" }}
                aria-hidden
              />
            )}
            <span>Sign in</span>
          </Button>
        </form>

        <p className="text-center text-xs text-[var(--ink-faint)]">
          Don&apos;t have an account?{" "}
          <Link
            href="/register"
            className="font-semibold text-[var(--primary)] hover:text-[var(--primary-hover)] transition-colors no-underline"
          >
            Create one now
          </Link>
        </p>
      </div>
    </main>
  );
}

export default function LoginPage() {
  return (
    <Suspense fallback={null}>
      <LoginForm />
    </Suspense>
  );
}
export const dynamic = "force-dynamic";
