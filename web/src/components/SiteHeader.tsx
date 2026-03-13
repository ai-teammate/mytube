"use client";

import { useState, useEffect, useRef, FormEvent } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { useAuth } from "@/context/AuthContext";
import { useTheme } from "@/context/ThemeContext";
import { LogoIcon, SunIcon, MoonIcon } from "@/components/icons";

/**
 * SiteHeader renders the global site header with branded logo, nav links,
 * theme toggle, search bar, and auth-aware navigation.
 * - Unauthenticated: shows nav links (My Videos redirects to login), login button.
 * - Authenticated: shows avatar with dropdown (Upload, My Videos, Account Settings, Sign out).
 */
export default function SiteHeader() {
  const [query, setQuery] = useState("");
  const [menuOpen, setMenuOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);
  const router = useRouter();
  const { user, loading, signOut, authError } = useAuth();
  const { theme, toggleTheme } = useTheme();

  useEffect(() => {
    if (!menuOpen) return;

    function handleClickOutside(e: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setMenuOpen(false);
      }
    }

    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [menuOpen]);

  useEffect(() => {
    if (!menuOpen) return;

    function handleKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") setMenuOpen(false);
    }

    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [menuOpen]);

  function handleSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const trimmed = query.trim();
    if (trimmed) {
      router.push(`/search?q=${encodeURIComponent(trimmed)}`);
    }
  }

  async function handleSignOut() {
    setMenuOpen(false);
    await signOut();
    router.replace("/login");
  }

  const displayName = user?.displayName || user?.email || "Account";
  // Unauthenticated users clicking "My Videos" are redirected to login with ?next param
  const myVideosHref = user ? "/dashboard" : "/login?next=/dashboard";

  return (
    <header
      style={{
        background: "var(--bg-header)",
        borderBottom: "1px solid rgba(127,127,127,0.16)",
      }}
      className="min-h-[56px] sm:min-h-[88px] px-4 sm:px-10 py-3 sm:py-4 flex items-center gap-3 sm:gap-6"
    >
      {/* Branded logo: SVG icon + text block */}
      <Link href="/" className="flex items-center gap-2 shrink-0">
        <LogoIcon
          className="w-11 h-11"
          style={{ color: "var(--accent-logo)" }}
        />
        <div className="flex flex-col leading-none gap-0.5">
          <span
            className="text-[22px] font-bold leading-none"
            style={{ color: "var(--accent-logo)" }}
          >
            MYTUBE
          </span>
          {/* Logo subtitle uses var(--text-subtle) per WCAG AA — see MYTUBE-475 */}
          <span
            className="text-[12px] uppercase tracking-wider leading-none"
            style={{ color: "var(--text-subtle)" }}
          >
            Personal Video Portal
          </span>
        </div>
      </Link>

      {/* Primary nav links — visible for all users */}
      <nav aria-label="Primary navigation" className="hidden sm:flex items-center gap-6">
        <Link
          href="/"
          className="text-base transition-colors hover:underline"
          style={{ color: "var(--text-secondary)" }}
        >
          Home
        </Link>
        <Link
          href={myVideosHref}
          className="text-base transition-colors hover:underline"
          style={{ color: "var(--text-secondary)" }}
        >
          My Videos
        </Link>
      </nav>

      {/* Search form — pill shape with purple focus accent */}
      <form
        onSubmit={handleSubmit}
        className="flex flex-1 min-w-0 max-w-xl"
        role="search"
        aria-label="Search videos"
      >
        <input
          type="search"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search videos…"
          aria-label="Search query"
          className="min-w-0 flex-1 border border-gray-300 rounded-l-full px-4 py-2 text-sm focus:outline-none focus:border-[color:var(--accent-logo)]"
        />
        <button
          type="submit"
          className="border border-l-0 border-gray-300 rounded-r-full px-4 py-2 bg-gray-50 hover:bg-gray-100 text-sm text-gray-700"
          aria-label="Submit search"
        >
          Search
        </button>
      </form>

      {/* Utility area: theme toggle + auth section */}
      <div className="ml-auto flex items-center gap-3 shrink-0">
        {/* Theme toggle — transparent ghost, focus ring uses accent-logo (see MYTUBE-473) */}
        <button
          type="button"
          onClick={toggleTheme}
          aria-label={`Switch to ${theme === "light" ? "dark" : "light"} mode`}
          className="w-10 h-10 rounded-full flex items-center justify-center bg-transparent transition-colors hover:bg-[color:var(--bg-card)] focus-visible:outline focus-visible:outline-2"
          style={{ outlineColor: "var(--accent-logo)" }}
        >
          {theme === "light" ? (
            <MoonIcon className="w-5 h-5" style={{ color: "var(--text-secondary)" }} />
          ) : (
            <SunIcon className="w-5 h-5" style={{ color: "var(--text-secondary)" }} />
          )}
        </button>

        {/* Auth section */}
        <nav aria-label="User navigation" className="shrink-0">
          {loading ? null : authError ? (
            <span role="alert" className="text-sm font-medium text-red-600">
              Authentication services are currently unavailable
            </span>
          ) : user ? (
            <div className="relative" ref={menuRef}>
              <button
                type="button"
                onClick={() => setMenuOpen((prev) => !prev)}
                aria-haspopup="true"
                aria-expanded={menuOpen}
                aria-label="User menu"
                className="flex items-center gap-2 text-sm font-medium rounded-full px-3 py-1.5 border transition-colors hover:opacity-90"
                style={{
                  borderColor: "var(--border-light)",
                  color: "var(--text-primary)",
                }}
              >
                {/* Avatar: gradient circle (--gradient-hero) with initial letter — see MYTUBE-477 */}
                <span
                  className="h-7 w-7 rounded-full text-white flex items-center justify-center text-xs font-bold select-none"
                  style={{ background: "var(--gradient-hero)" }}
                  aria-hidden="true"
                >
                  {displayName[0].toUpperCase()}
                </span>
                <span className="hidden sm:inline max-w-[120px] truncate">{displayName}</span>
              </button>

              {menuOpen && (
                <div
                  role="menu"
                  className="absolute right-0 mt-2 w-48 rounded-xl shadow-lg border py-1 z-50"
                  style={{
                    background: "var(--bg-content)",
                    borderColor: "var(--border-light)",
                  }}
                >
                  <Link
                    href="/upload"
                    role="menuitem"
                    onClick={() => setMenuOpen(false)}
                    className="block px-4 py-2 text-sm hover:bg-[color:var(--bg-card)]"
                    style={{ color: "var(--text-primary)" }}
                  >
                    Upload
                  </Link>
                  <Link
                    href="/dashboard"
                    role="menuitem"
                    onClick={() => setMenuOpen(false)}
                    className="block px-4 py-2 text-sm hover:bg-[color:var(--bg-card)]"
                    style={{ color: "var(--text-primary)" }}
                  >
                    My Videos
                  </Link>
                  <Link
                    href="/settings"
                    role="menuitem"
                    onClick={() => setMenuOpen(false)}
                    className="block px-4 py-2 text-sm hover:bg-[color:var(--bg-card)]"
                    style={{ color: "var(--text-primary)" }}
                  >
                    Account Settings
                  </Link>
                  <hr className="my-1" style={{ borderColor: "var(--border-light)" }} />
                  <button
                    type="button"
                    role="menuitem"
                    onClick={handleSignOut}
                    className="w-full text-left px-4 py-2 text-sm text-red-600 hover:bg-[color:var(--bg-card)]"
                  >
                    Sign out
                  </button>
                </div>
              )}
            </div>
          ) : (
            /* Login button: pill shape, branded border/colour, semibold */
            <Link
              href="/login"
              className="text-sm font-semibold rounded-full px-4 py-1.5 border transition-colors hover:opacity-80"
              style={{
                borderColor: "var(--accent-login-border)",
                color: "var(--accent-logo)",
              }}
            >
              Sign in
            </Link>
          )}
        </nav>
      </div>
    </header>
  );
}
