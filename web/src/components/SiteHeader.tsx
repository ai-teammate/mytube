"use client";

import { useState, useEffect, useRef, FormEvent } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { useAuth } from "@/context/AuthContext";

/**
 * SiteHeader renders the global site header with a search bar and auth-aware navigation.
 * - Unauthenticated: shows a "Sign in" button.
 * - Authenticated: shows a user menu with links to Upload, My Videos, Account Settings, and Sign out.
 */
export default function SiteHeader() {
  const [query, setQuery] = useState("");
  const [menuOpen, setMenuOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);
  const router = useRouter();
  const { user, loading, signOut } = useAuth();

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

  return (
    <header className="bg-white border-b border-gray-200 px-4 py-3 flex items-center gap-4">
      <a href="/" className="text-xl font-bold text-red-600 shrink-0">
        mytube
      </a>

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

      <nav aria-label="User navigation" className="ml-auto shrink-0">
        {loading ? null : user ? (
          <div className="relative" ref={menuRef}>
            <button
              type="button"
              onClick={() => setMenuOpen((prev) => !prev)}
              aria-haspopup="true"
              aria-expanded={menuOpen}
              aria-label="User menu"
              className="flex items-center gap-2 text-sm font-medium text-gray-700 hover:text-gray-900 rounded-full px-3 py-1.5 border border-gray-200 hover:bg-gray-50 transition-colors"
            >
              <span
                className="h-7 w-7 rounded-full bg-blue-600 text-white flex items-center justify-center text-xs font-bold select-none"
                aria-hidden="true"
              >
                {displayName[0].toUpperCase()}
              </span>
              <span className="hidden sm:inline max-w-[120px] truncate">{displayName}</span>
            </button>

            {menuOpen && (
              <div
                role="menu"
                className="absolute right-0 mt-2 w-48 rounded-xl bg-white shadow-lg border border-gray-100 py-1 z-50"
              >
                <Link
                  href="/upload"
                  role="menuitem"
                  onClick={() => setMenuOpen(false)}
                  className="block px-4 py-2 text-sm text-gray-700 hover:bg-gray-50"
                >
                  Upload
                </Link>
                <Link
                  href="/dashboard"
                  role="menuitem"
                  onClick={() => setMenuOpen(false)}
                  className="block px-4 py-2 text-sm text-gray-700 hover:bg-gray-50"
                >
                  My Videos
                </Link>
                <Link
                  href="/settings"
                  role="menuitem"
                  onClick={() => setMenuOpen(false)}
                  className="block px-4 py-2 text-sm text-gray-700 hover:bg-gray-50"
                >
                  Account Settings
                </Link>
                <hr className="my-1 border-gray-100" />
                <button
                  type="button"
                  role="menuitem"
                  onClick={handleSignOut}
                  className="w-full text-left px-4 py-2 text-sm text-red-600 hover:bg-gray-50"
                >
                  Sign out
                </button>
              </div>
            )}
          </div>
        ) : (
          <Link
            href="/login"
            className="text-sm font-medium text-blue-600 hover:text-blue-700 border border-blue-200 rounded-full px-4 py-1.5 hover:bg-blue-50 transition-colors"
          >
            Sign in
          </Link>
        )}
      </nav>
    </header>
  );
}
