"use client";

import React, { ReactNode, useEffect } from "react";
import { useRouter, usePathname, useSearchParams } from "next/navigation";
import { useAuth } from "@/context/AuthContext";

interface RequireAuthProps {
  children: ReactNode;
}

/**
 * RequireAuth wraps protected pages.
 * - While Firebase auth state is resolving: renders a full-page spinner.
 * - When unauthenticated: redirects to /login?next=<current_path_and_query>.
 * - When authenticated: renders children.
 */
export default function RequireAuth({ children }: RequireAuthProps) {
  const { user, loading } = useAuth();
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();

  useEffect(() => {
    if (!loading && !user) {
      const qs = searchParams?.toString();
      const fullPath = qs ? `${pathname}?${qs}` : (pathname ?? "/");
      const next = encodeURIComponent(fullPath);
      router.replace(`/login?next=${next}`);
    }
  }, [user, loading, router, pathname, searchParams]);

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="flex flex-col items-center gap-3">
          <div
            className="h-8 w-8 animate-spin rounded-full border-4 border-blue-600 border-t-transparent"
            aria-hidden="true"
          />
          <p className="text-sm text-gray-600">Loading…</p>
        </div>
      </div>
    );
  }

  if (!user) {
    // Redirect is in-flight; render nothing to avoid flash.
    return null;
  }

  return <>{children}</>;
}
