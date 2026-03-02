"use client";

import { useState, FormEvent } from "react";
import { useRouter } from "next/navigation";

/**
 * SiteHeader renders the global site header with a search bar.
 * The search bar submits to /search?q=<query>.
 */
export default function SiteHeader() {
  const [query, setQuery] = useState("");
  const router = useRouter();

  function handleSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const trimmed = query.trim();
    if (trimmed) {
      router.push(`/search?q=${encodeURIComponent(trimmed)}`);
    }
  }

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
    </header>
  );
}
