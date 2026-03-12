"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { createUserWithEmailAndPassword } from "firebase/auth";
import { getFirebaseAuth } from "@/lib/firebase";
import { useAuth } from "@/context/AuthContext";
import LogoIcon from "@/components/icons/LogoIcon";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "";

// ─── Google "G" SVG ──────────────────────────────────────────────────────────

function GoogleIcon() {
  return (
    <svg className="h-5 w-5 shrink-0" viewBox="0 0 24 24" aria-hidden="true">
      <path
        d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
        fill="#4285F4"
      />
      <path
        d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
        fill="#34A853"
      />
      <path
        d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l3.66-2.84z"
        fill="#FBBC05"
      />
      <path
        d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"
        fill="#EA4335"
      />
    </svg>
  );
}

// ─── GitHub mark SVG ─────────────────────────────────────────────────────────

function GitHubIcon() {
  return (
    <svg className="h-5 w-5 shrink-0" viewBox="0 0 24 24" aria-hidden="true" fill="currentColor">
      <path d="M12 0C5.37 0 0 5.37 0 12c0 5.31 3.435 9.795 8.205 11.385.6.105.825-.255.825-.57 0-.285-.015-1.23-.015-2.235-3.015.555-3.795-.735-4.035-1.41-.135-.345-.72-1.41-1.23-1.695-.42-.225-1.02-.78-.015-.795.945-.015 1.62.87 1.845 1.23 1.08 1.815 2.805 1.305 3.495.99.105-.78.42-1.305.765-1.605-2.67-.3-5.46-1.335-5.46-5.925 0-1.305.465-2.385 1.23-3.225-.12-.3-.54-1.53.12-3.18 0 0 1.005-.315 3.3 1.23.96-.27 1.98-.405 3-.405s2.04.135 3 .405c2.295-1.56 3.3-1.23 3.3-1.23.66 1.65.24 2.88.12 3.18.765.84 1.23 1.905 1.23 3.225 0 4.605-2.805 5.625-5.475 5.925.435.375.81 1.095.81 2.22 0 1.605-.015 2.895-.015 3.3 0 .315.225.69.825.57A12.02 12.02 0 0 0 24 12c0-6.63-5.37-12-12-12z" />
    </svg>
  );
}

// ─── Auth logo ────────────────────────────────────────────────────────────────

function AuthCardLogo() {
  return (
    <div className="flex items-center justify-center gap-2 mb-6">
      <LogoIcon
        style={{ width: 48, height: 48, color: "var(--accent-logo)" }}
        aria-hidden
      />
      <span
        className="text-xl font-bold tracking-wide"
        style={{ color: "var(--accent-logo)" }}
      >
        MYTUBE
      </span>
    </div>
  );
}

// ─── Page component ───────────────────────────────────────────────────────────

export default function RegisterPage() {
  const router = useRouter();
  const { user, loading } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (!loading && user) {
      router.replace("/");
    }
  }, [user, loading, router]);

  async function handleRegister(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      const auth = getFirebaseAuth();
      const credential = await createUserWithEmailAndPassword(
        auth,
        email,
        password
      );
      const token = await credential.user.getIdToken();
      const res = await fetch(`${API_URL}/api/me`, {
        method: "GET",
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) {
        console.warn("Backend user provisioning failed:", res.status);
      }
      router.replace("/");
    } catch (err: unknown) {
      setError(getFirebaseErrorMessage(err));
    } finally {
      setSubmitting(false);
    }
  }

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center" style={{ background: "var(--bg-page)" }}>
        <p style={{ color: "var(--text-secondary)" }}>Loading…</p>
      </div>
    );
  }

  return (
    <div
      className="min-h-screen flex items-center justify-center px-4 py-8"
      style={{ background: "var(--bg-page)" }}
    >
      <div
        className="auth-card w-full"
        style={{
          background: "var(--bg-login)",
          borderRadius: 24,
          border: "1.5px solid var(--accent-login-border)",
          boxShadow: "var(--shadow-main)",
          padding: "40px 36px",
          maxWidth: 400,
        }}
      >
        <AuthCardLogo />

        <h1
          className="text-center font-bold mb-6"
          style={{ fontSize: 22, fontWeight: 700, color: "var(--text-primary)" }}
        >
          Welcome to MyTube
        </h1>

        {error && (
          <div
            role="alert"
            className="rounded-xl px-4 py-3 text-sm mb-4"
            style={{
              background: "#fef2f2",
              border: "1px solid #fecaca",
              color: "#dc2626",
            }}
          >
            {error}
          </div>
        )}

        {/* Social login buttons */}
        <div className="flex flex-col gap-3 mb-5">
          <button
            type="button"
            disabled
            title="Coming soon"
            className="auth-btn flex items-center justify-center gap-3 w-full font-medium opacity-50 cursor-not-allowed"
            style={{
              border: "1.5px solid var(--border-light)",
              borderRadius: 12,
              padding: "12px 16px",
              background: "var(--bg-content)",
              fontWeight: 500,
              color: "var(--text-primary)",
            }}
          >
            <GoogleIcon />
            Sign up with Google
          </button>

          <button
            type="button"
            disabled
            title="Coming soon"
            className="auth-btn flex items-center justify-center gap-3 w-full font-medium opacity-50 cursor-not-allowed"
            style={{
              border: "1.5px solid var(--border-light)",
              borderRadius: 12,
              padding: "12px 16px",
              background: "var(--bg-content)",
              fontWeight: 500,
              color: "var(--text-primary)",
            }}
          >
            <GitHubIcon />
            Sign up with GitHub
          </button>
        </div>

        {/* Divider */}
        <div className="relative flex items-center my-5">
          <div className="flex-1" style={{ borderTop: "1px solid var(--border-light)" }} />
          <span className="px-3 text-xs uppercase" style={{ color: "var(--text-subtle)" }}>
            or
          </span>
          <div className="flex-1" style={{ borderTop: "1px solid var(--border-light)" }} />
        </div>

        {/* Email/password form */}
        <form onSubmit={handleRegister} className="flex flex-col gap-4">
          <div>
            <label
              htmlFor="email"
              className="block text-sm font-medium mb-1"
              style={{ color: "var(--text-primary)" }}
            >
              Email
            </label>
            <input
              id="email"
              type="email"
              autoComplete="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@example.com"
              className="w-full text-sm focus:outline-none transition-shadow"
              style={{
                background: "var(--bg-page)",
                borderRadius: 12,
                border: "1.5px solid var(--border-light)",
                padding: "10px 14px",
                color: "var(--text-primary)",
              }}
              onFocus={(e) => {
                e.currentTarget.style.boxShadow = "0 0 0 3px rgba(109,64,203,0.25)";
                e.currentTarget.style.borderColor = "var(--accent-logo)";
              }}
              onBlur={(e) => {
                e.currentTarget.style.boxShadow = "";
                e.currentTarget.style.borderColor = "var(--border-light)";
              }}
            />
          </div>

          <div>
            <label
              htmlFor="password"
              className="block text-sm font-medium mb-1"
              style={{ color: "var(--text-primary)" }}
            >
              Password
            </label>
            <input
              id="password"
              type="password"
              autoComplete="new-password"
              required
              minLength={6}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••"
              className="w-full text-sm focus:outline-none transition-shadow"
              style={{
                background: "var(--bg-page)",
                borderRadius: 12,
                border: "1.5px solid var(--border-light)",
                padding: "10px 14px",
                color: "var(--text-primary)",
              }}
              onFocus={(e) => {
                e.currentTarget.style.boxShadow = "0 0 0 3px rgba(109,64,203,0.25)";
                e.currentTarget.style.borderColor = "var(--accent-logo)";
              }}
              onBlur={(e) => {
                e.currentTarget.style.boxShadow = "";
                e.currentTarget.style.borderColor = "var(--border-light)";
              }}
            />
            <p className="mt-1 text-xs" style={{ color: "var(--text-subtle)" }}>
              Minimum 6 characters
            </p>
          </div>

          <button
            type="submit"
            disabled={submitting}
            className="btn cta w-full text-sm font-semibold disabled:opacity-50 disabled:cursor-not-allowed transition-opacity"
            style={{
              background: "var(--gradient-cta)",
              borderRadius: 999,
              padding: "12px 16px",
              color: "var(--text-cta)",
              fontWeight: 600,
              border: "none",
            }}
          >
            {submitting ? "Creating account…" : "Create account"}
          </button>
        </form>

        <p className="text-center text-sm mt-5" style={{ color: "var(--text-secondary)" }}>
          Already have an account?{" "}
          <Link
            href="/login"
            className="font-medium hover:underline"
            style={{ color: "var(--accent-logo)" }}
          >
            Sign in
          </Link>
        </p>
      </div>
    </div>
  );
}

// ─── Firebase error messages ──────────────────────────────────────────────────

function getFirebaseErrorMessage(err: unknown): string {
  if (err && typeof err === "object" && "code" in err) {
    const code = (err as { code: string }).code;
    switch (code) {
      case "auth/email-already-in-use":
        return "An account with this email already exists.";
      case "auth/invalid-email":
        return "Invalid email address.";
      case "auth/weak-password":
        return "Password must be at least 6 characters.";
      default:
        return "Registration failed. Please try again.";
    }
  }
  return "An unexpected error occurred.";
}

