"use client";

import { useState, useEffect, useRef } from "react";
import type { PlaylistRepository, PlaylistSummary } from "@/domain/playlist";

interface SaveToPlaylistProps {
  videoID: string;
  repository: PlaylistRepository;
  getToken: () => Promise<string | null>;
  /** When true, the button is not shown (user is not authenticated). */
  hidden?: boolean;
}

/**
 * SaveToPlaylist renders a "Save to playlist" button that opens a dropdown.
 *
 * When the user has no playlists, an inline "＋ New playlist" entry allows
 * creating one without leaving the page (Option A: inline create).
 *
 * Icon style: filled icon for the primary button (mixed style, Option C).
 */
export default function SaveToPlaylist({
  videoID,
  repository,
  getToken,
  hidden = false,
}: SaveToPlaylistProps) {
  const [open, setOpen] = useState(false);
  const [playlists, setPlaylists] = useState<PlaylistSummary[] | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Inline create state.
  const [creatingNew, setCreatingNew] = useState(false);
  const [newTitle, setNewTitle] = useState("");
  const [creating, setCreating] = useState(false);

  // Feedback after saving.
  const [savedPlaylistID, setSavedPlaylistID] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  const dropdownRef = useRef<HTMLDivElement>(null);

  // Close dropdown on outside click.
  useEffect(() => {
    if (!open) return;
    function handleClick(e: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, [open]);

  async function loadPlaylists() {
    setLoading(true);
    setError(null);
    try {
      const token = await getToken();
      if (!token) {
        setError("Please sign in.");
        return;
      }
      const data = await repository.listMine(token);
      setPlaylists(data);
    } catch {
      setError("Could not load playlists.");
    } finally {
      setLoading(false);
    }
  }

  function handleToggle() {
    const next = !open;
    setOpen(next);
    if (next && playlists === null) {
      loadPlaylists();
    }
  }

  async function handleSaveToPlaylist(playlistID: string) {
    setSaving(true);
    setSavedPlaylistID(null);
    setError(null);
    try {
      const token = await getToken();
      if (!token) {
        setError("Please sign in.");
        return;
      }
      await repository.addVideo(playlistID, videoID, token);
      setSavedPlaylistID(playlistID);
      setTimeout(() => {
        setOpen(false);
        setSavedPlaylistID(null);
      }, 800);
    } catch {
      setError("Failed to save to playlist.");
    } finally {
      setSaving(false);
    }
  }

  async function handleCreatePlaylist() {
    const title = newTitle.trim();
    if (!title) return;

    setCreating(true);
    setError(null);
    try {
      const token = await getToken();
      if (!token) {
        setError("Please sign in.");
        return;
      }
      const created = await repository.create(title, token);
      // Add to the list and immediately save this video to it.
      setPlaylists((prev) => (prev ? [created, ...prev] : [created]));
      setNewTitle("");
      setCreatingNew(false);
      await handleSaveToPlaylist(created.id);
    } catch {
      setError("Failed to create playlist.");
    } finally {
      setCreating(false);
    }
  }

  if (hidden) return null;

  return (
    <div className="relative inline-block" ref={dropdownRef}>
      {/* Primary "Save to playlist" button — filled icon (Option C) */}
      <button
        onClick={handleToggle}
        aria-label="Save to playlist"
        aria-expanded={open}
        className="inline-flex items-center gap-1.5 rounded-lg bg-gray-100 hover:bg-gray-200 px-3 py-1.5 text-sm font-medium text-gray-700 transition-colors"
      >
        {/* Filled bookmark icon */}
        <svg
          xmlns="http://www.w3.org/2000/svg"
          viewBox="0 0 24 24"
          fill="currentColor"
          className="w-4 h-4"
          aria-hidden="true"
        >
          <path
            fillRule="evenodd"
            d="M6.32 2.577a49.255 49.255 0 0111.36 0c1.497.174 2.57 1.46 2.57 2.93V21a.75.75 0 01-1.085.67L12 18.089l-7.165 3.583A.75.75 0 013.75 21V5.507c0-1.47 1.073-2.756 2.57-2.93z"
            clipRule="evenodd"
          />
        </svg>
        Save
      </button>

      {/* Dropdown */}
      {open && (
        <div
          role="menu"
          className="absolute z-50 mt-1 w-64 bg-white rounded-lg shadow-lg border border-gray-200 overflow-hidden"
        >
          <div className="px-3 py-2 border-b border-gray-100">
            <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide">
              Save to playlist
            </p>
          </div>

          {loading ? (
            <p className="px-3 py-4 text-sm text-gray-400 text-center">
              Loading…
            </p>
          ) : error ? (
            <p role="alert" className="px-3 py-3 text-sm text-red-600">
              {error}
            </p>
          ) : (
            <>
              {/* Playlist items */}
              {playlists && playlists.length > 0 ? (
                <ul className="max-h-48 overflow-y-auto">
                  {playlists.map((pl) => (
                    <li key={pl.id}>
                      <button
                        onClick={() => handleSaveToPlaylist(pl.id)}
                        disabled={saving}
                        className={`w-full text-left px-3 py-2 text-sm hover:bg-gray-50 transition-colors flex items-center justify-between disabled:opacity-50 ${
                          savedPlaylistID === pl.id ? "text-green-600 font-medium" : "text-gray-700"
                        }`}
                        role="menuitem"
                      >
                        <span className="truncate">{pl.title}</span>
                        {savedPlaylistID === pl.id && (
                          <span className="text-green-500" aria-label="Saved">✓</span>
                        )}
                      </button>
                    </li>
                  ))}
                </ul>
              ) : (
                !creatingNew && (
                  <p className="px-3 py-2 text-sm text-gray-400">
                    No playlists yet
                  </p>
                )
              )}

              {/* Inline create (Option A) */}
              {creatingNew ? (
                <div className="px-3 py-2 border-t border-gray-100">
                  <input
                    type="text"
                    value={newTitle}
                    onChange={(e) => setNewTitle(e.target.value)}
                    placeholder="Playlist name"
                    autoFocus
                    maxLength={255}
                    className="w-full rounded border border-gray-300 px-2 py-1 text-sm mb-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
                    onKeyDown={(e) => {
                      if (e.key === "Enter") handleCreatePlaylist();
                      if (e.key === "Escape") {
                        setCreatingNew(false);
                        setNewTitle("");
                      }
                    }}
                  />
                  <div className="flex gap-2">
                    <button
                      onClick={handleCreatePlaylist}
                      disabled={creating || !newTitle.trim()}
                      className="flex-1 rounded bg-blue-600 px-2 py-1 text-xs font-semibold text-white hover:bg-blue-700 disabled:opacity-50"
                    >
                      {creating ? "Creating…" : "Create"}
                    </button>
                    <button
                      onClick={() => {
                        setCreatingNew(false);
                        setNewTitle("");
                      }}
                      disabled={creating}
                      className="flex-1 rounded border border-gray-300 px-2 py-1 text-xs text-gray-600 hover:bg-gray-50 disabled:opacity-50"
                    >
                      Cancel
                    </button>
                  </div>
                </div>
              ) : (
                <div className="border-t border-gray-100">
                  <button
                    onClick={() => setCreatingNew(true)}
                    className="w-full text-left px-3 py-2 text-sm text-blue-600 hover:bg-gray-50 transition-colors flex items-center gap-1.5"
                    role="menuitem"
                  >
                    {/* Outline plus icon (secondary action, Option C) */}
                    <svg
                      xmlns="http://www.w3.org/2000/svg"
                      fill="none"
                      viewBox="0 0 24 24"
                      strokeWidth={1.5}
                      stroke="currentColor"
                      className="w-4 h-4"
                      aria-hidden="true"
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        d="M12 4.5v15m7.5-7.5h-15"
                      />
                    </svg>
                    New playlist
                  </button>
                </div>
              )}
            </>
          )}
        </div>
      )}
    </div>
  );
}
