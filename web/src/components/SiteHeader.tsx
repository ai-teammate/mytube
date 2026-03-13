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
  const [mobileNavOpen, setMobileNavOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);
  const mobileNavRef = useRef<HTMLElement>(null);
  const hamburgerRef = useRef<HTMLButtonElement>(null);
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

  // Close mobile nav on Escape key (WCAG 2.1 SC 2.1.1 Keyboard)
  useEffect(() => {
    if (!mobileNavOpen) return;

    function handleKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") setMobileNavOpen(false);
    }

    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [mobileNavOpen]);

  // Close mobile nav when clicking outside (consistent with user-dropdown behaviour)
  useEffect(() => {
    if (!mobileNavOpen) return;

    function handleClickOutside(e: MouseEvent) {
      if (
        mobileNavRef.current && !mobileNavRef.current.contains(e.target as Node) &&
        hamburgerRef.current && !hamburgerRef.current.contains(e.target as Node)
      ) {
        setMobileNavOpen(false);
      }
    }

    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [mobileNavOpen]);

  // Reset mobile nav state when viewport grows past the sm breakpoint (640px)
  useEffect(() => {
    function handleResize() {
      if (window.innerWidth >= 640) setMobileNavOpen(false);
    }

    window.addEventListener("resize", handleResize);
    return () => window.removeEventListener("resize", handleResize);
  }, []);

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
    <>
    <header
      style={{
        background: "var(--bg-header)",
        borderBottom: "1px solid rgba(127,127,127,0.16)",
      }}
      className="min-h-[56px] sm:min-h-[88px] px-4 sm:px-10 py-3 sm:py-4 flex items-center gap-3 sm:gap-6"
    >
      {/* Hamburger toggle — mobile only */}
      <button
        ref={hamburgerRef}
        type="button"
        className="sm:hidden w-10 h-10 flex items-center justify-center rounded-md bg-transparent transition-colors hover:bg-[color:var(--bg-card)] shrink-0"
        aria-label={mobileNavOpen ? "Close navigation menu" : "Open navigation menu"}
        aria-expanded={mobileNavOpen}
        aria-controls="mobile-nav"
        onClick={() => setMobileNavOpen((prev) => !prev)}
      >
        {mobileNavOpen ? (
          /* X icon */
          <svg xmlns="http://www.w3.org/2000/svg" width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" style={{ color: "var(--text-secondary)" }}>
            <line x1="18" y1="6" x2="6" y2="18" />
            <line x1="6" y1="6" x2="18" y2="18" />
          </svg>
        ) : (
          /* Hamburger icon */
          <svg xmlns="http://www.w3.org/2000/svg" width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" style={{ color: "var(--text-secondary)" }}>
            <line x1="3" y1="6" x2="21" y2="6" />
            <line x1="3" y1="12" x2="21" y2="12" />
            <line x1="3" y1="18" x2="21" y2="18" />
          </svg>
        )}
      </button>

      {/* Branded logo: SVG icon + text block */}
      <Link href="/" aria-label="MYTUBE — Personal Video Portal" className="flex items-center gap-2 shrink-0">
        <LogoIcon
          className="w-11 h-11"
          style={{ color: "var(--accent-logo)" }}
        />
        <div className="hidden sm:flex flex-col leading-none gap-0.5">
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

      {/* Primary nav links — visible on sm+ */}
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

    {/* Mobile navigation panel — always in DOM; hidden attribute controls visibility for AT and aria-controls */}
    <nav
      ref={mobileNavRef}
      id="mobile-nav"
      aria-label="Mobile navigation"
      hidden={!mobileNavOpen}
      className="sm:hidden border-b px-4 py-3 flex flex-col gap-3"
      style={{
        background: "var(--bg-header)",
        borderColor: "rgba(127,127,127,0.16)",
      }}
    >
      <Link
        href="/"
        className="text-base transition-colors hover:underline py-1"
        style={{ color: "var(--text-secondary)" }}
        onClick={() => setMobileNavOpen(false)}
      >
        Home
      </Link>
      <Link
        href={myVideosHref}
        className="text-base transition-colors hover:underline py-1"
        style={{ color: "var(--text-secondary)" }}
        onClick={() => setMobileNavOpen(false)}
      >
        My Videos
      </Link>
    </nav>
    </>
  );
}
