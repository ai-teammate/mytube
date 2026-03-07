"use client";

import { useState, FormEvent } from "react";
import { useRouter, usePathname } from "next/navigation";
import Link from "next/link";
import { useAuth } from "@/context/AuthContext";

/**
 * SiteHeader renders the global site header with a logo, search bar,
 * primary navigation links, and a responsive hamburger menu for mobile.
 * Auth-only links (Upload, My Videos, Playlists) are only shown to
 * authenticated users. Includes a Sign out button for authenticated users.
 */
export default function SiteHeader() {
  const [query, setQuery] = useState("");
  const [menuOpen, setMenuOpen] = useState(false);
  const router = useRouter();
  const pathname = usePathname();
  const { user, signOut } = useAuth();

  function handleSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const trimmed = query.trim();
    if (trimmed) {
      router.push(`/search?q=${encodeURIComponent(trimmed)}`);
    }
  }

  function isActive(href: string) {
    return pathname === href;
  }

  const navLinkClass = (href: string) =>
    `text-sm font-medium transition-colors ${
      isActive(href)
        ? "text-red-600"
        : "text-gray-700 hover:text-red-600"
    }`;

  return (
    <header className="bg-white border-b border-gray-200 px-4 py-3">
      <div className="flex items-center gap-4">
        {/* Logo */}
        <Link href="/" className="text-xl font-bold text-red-600 shrink-0">
          mytube
        </Link>

        {/* Search bar */}
        <form
          onSubmit={handleSubmit}
          className="flex flex-1 max-w-xl"
          role="search"
          aria-label="Search videos"
        >
          <input
            type="search"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search videos…"
            aria-label="Search query"
            className="flex-1 border border-gray-300 rounded-l-full px-4 py-2 text-sm focus:outline-none focus:border-blue-500"
          />
          <button
            type="submit"
            className="border border-l-0 border-gray-300 rounded-r-full px-4 py-2 bg-gray-50 hover:bg-gray-100 text-sm"
            aria-label="Submit search"
          >
            Search
          </button>
        </form>

        {/* Desktop nav — hidden on mobile */}
        <nav aria-label="Primary navigation" className="hidden md:flex items-center gap-6">
          <Link href="/" className={navLinkClass("/")}>Home</Link>
          {user && (
            <>
              <Link href="/upload" className={navLinkClass("/upload")}>Upload</Link>
              <Link href="/dashboard" className={navLinkClass("/dashboard")}>My Videos</Link>
              <Link href="/dashboard" className={navLinkClass("/dashboard")}>Playlists</Link>
            </>
          )}
        </nav>

        {/* Sign out (desktop, auth only) */}
        {user && (
          <button
            onClick={signOut}
            className="hidden md:inline-flex text-sm font-medium text-gray-700 hover:text-red-600 transition-colors shrink-0"
          >
            Sign out
          </button>
        )}

        {/* Hamburger button — visible on mobile only */}
        <button
          type="button"
          aria-label={menuOpen ? "Close menu" : "Open menu"}
          aria-expanded={menuOpen}
          aria-controls="mobile-menu"
          onClick={() => setMenuOpen((prev) => !prev)}
          className="md:hidden ml-auto p-2 rounded text-gray-700 hover:bg-gray-100 focus:outline-none focus:ring-2 focus:ring-red-500"
        >
          {menuOpen ? (
            /* Close (X) icon */
            <svg
              className="w-6 h-6"
              fill="none"
              stroke="currentColor"
              strokeWidth={1.5}
              strokeLinecap="round"
              strokeLinejoin="round"
              viewBox="0 0 24 24"
              aria-hidden="true"
            >
              <path d="M6 18L18 6M6 6l12 12" />
            </svg>
          ) : (
            /* Hamburger icon */
            <svg
              className="w-6 h-6"
              fill="none"
              stroke="currentColor"
              strokeWidth={1.5}
              strokeLinecap="round"
              strokeLinejoin="round"
              viewBox="0 0 24 24"
              aria-hidden="true"
            >
              <path d="M3 12h18M3 6h18M3 18h18" />
            </svg>
          )}
        </button>
      </div>

      {/* Mobile nav menu */}
      {menuOpen && (
        <nav
          id="mobile-menu"
          aria-label="Mobile navigation"
          className="md:hidden mt-3 flex flex-col gap-3 pb-2"
        >
          <Link
            href="/"
            className={navLinkClass("/")}
            onClick={() => setMenuOpen(false)}
          >
            Home
          </Link>
          {user && (
            <>
              <Link
                href="/upload"
                className={navLinkClass("/upload")}
                onClick={() => setMenuOpen(false)}
              >
                Upload
              </Link>
              <Link
                href="/dashboard"
                className={navLinkClass("/dashboard")}
                onClick={() => setMenuOpen(false)}
              >
                My Videos
              </Link>
              <Link
                href="/dashboard"
                className={navLinkClass("/dashboard")}
                onClick={() => setMenuOpen(false)}
              >
                Playlists
              </Link>
              <button
                onClick={() => {
                  setMenuOpen(false);
                  signOut();
                }}
                className="text-sm font-medium text-gray-700 hover:text-red-600 transition-colors text-left"
              >
                Sign out
              </button>
            </>
          )}
        </nav>
      )}
    </header>
  );
}
