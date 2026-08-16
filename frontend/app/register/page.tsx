"use client";

import { FormEvent, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Loader2 } from "lucide-react";

import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";

export default function RegisterPage() {
  const { register, status } = useAuth();
  const router = useRouter();

  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (status === "authenticated") {
      router.replace("/dashboard");
    }
  }, [status, router]);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);

    if (password !== confirm) {
      setError("Passwords do not match.");
      return;
    }
    if (password.length < 8) {
      setError("Password must be at least 8 characters long.");
      return;
    }

    setSubmitting(true);
    try {
      await register(name, email, password);
      router.push("/login?registered=1");
    } catch (err) {
      setError(
        err instanceof ApiError
          ? err.message
          : "Unable to create an account. Please try again."
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
            Create an account
          </h1>
          <p className="text-xs text-[var(--ink-faint)]">
            Register to query and manage university policy documents.
          </p>
        </div>

        {/* Card Form */}
        <form
          onSubmit={handleSubmit}
          className="space-y-5 rounded-[var(--radius-lg)] border border-[var(--edge)] bg-[var(--canvas-raised)] p-7 shadow-[var(--shadow-md)]"
        >
          {error && <Alert variant="error">{error}</Alert>}

          {/* Name */}
          <div className="space-y-1.5">
            <label
              htmlFor="name"
              className="text-xs font-semibold text-[var(--ink-muted)]"
            >
              Full name
            </label>
            <Input
              id="name"
              type="text"
              required
              autoComplete="name"
              placeholder="e.g. Jane Doe"
              value={name}
              onChange={(e) => setName(e.target.value)}
              disabled={submitting}
            />
          </div>

          {/* Email */}
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

          {/* Password */}
          <div className="space-y-1.5">
            <div className="flex items-center justify-between">
              <label
                htmlFor="password"
                className="text-xs font-semibold text-[var(--ink-muted)]"
              >
                Password
              </label>
              <span className="text-[10px] text-[var(--ink-ghost)]">Min. 8 characters</span>
            </div>
            <Input
              id="password"
              type="password"
              required
              autoComplete="new-password"
              placeholder="At least 8 characters"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              disabled={submitting}
            />
          </div>

          {/* Confirm Password */}
          <div className="space-y-1.5">
            <label
              htmlFor="confirm"
              className="text-xs font-semibold text-[var(--ink-muted)]"
            >
              Confirm password
            </label>
            <Input
              id="confirm"
              type="password"
              required
              autoComplete="new-password"
              placeholder="Re-enter your password"
              value={confirm}
              onChange={(e) => setConfirm(e.target.value)}
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
            <span>Register</span>
          </Button>
        </form>

        <p className="text-center text-xs text-[var(--ink-faint)]">
          Already have an account?{" "}
          <Link
            href="/login"
            className="font-semibold text-[var(--primary)] hover:text-[var(--primary-hover)] transition-colors no-underline"
          >
            Sign in instead
          </Link>
        </p>
      </div>
    </main>
  );
}
export const dynamic = "force-dynamic";
