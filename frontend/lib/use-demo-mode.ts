"use client";

/**
 * Runtime demo-mode detection for the frontend.
 *
 * The backend advertises whether it is running in public Demo Mode via the
 * unauthenticated `GET /api/demo/info` endpoint. This hook reads that at
 * runtime so a single frontend build serves both modes without a build-time
 * flag:
 *
 *   DEMO_MODE=true  -> demo info returns demo_mode: true (public demo UI)
 *   DEMO_MODE=false -> demo info returns 404  (normal authenticated app)
 *
 * It is safe for the public demo: when no demo is active it simply reports
 * false and the normal authenticated flow is used.
 */

import { useEffect, useState } from "react";

import { getDemoInfo, type DemoInfo } from "@/lib/demo";

interface DemoModeState {
  /** True once the backend reports a ready public demo. */
  isDemo: boolean;
  /** Null while the demo-info request is still in flight. */
  loading: boolean;
  /** The raw demo info when the backend is in demo mode, else null. */
  info: DemoInfo | null;
}

export function useDemoMode(): DemoModeState {
  const [state, setState] = useState<DemoModeState>({
    isDemo: false,
    loading: true,
    info: null,
  });

  useEffect(() => {
    let cancelled = false;
    getDemoInfo()
      .then((info) => {
        if (!cancelled) {
          setState({ isDemo: info.demo_mode, loading: false, info });
        }
      })
      .catch(() => {
        // 404 (DEMO_MODE off) or network error: not a demo deployment.
        if (!cancelled) {
          setState({ isDemo: false, loading: false, info: null });
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return state;
}
