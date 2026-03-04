"use client";

import { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useAuth } from "@/context/AuthContext";
import {
  ApiDashboardVideoRepository,
  ApiVideoManagementRepository,
} from "@/data/dashboardRepository";
import { ApiPlaylistRepository } from "@/data/playlistRepository";
import type {
  DashboardVideo,
  DashboardVideoRepository,
  UpdateVideoParams,
  VideoManagementRepository,
} from "@/domain/dashboard";
import type { PlaylistRepository, PlaylistSummary } from "@/domain/playlist";
import { CATEGORIES } from "@/domain/categories";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "";

export const defaultDashboardRepo = new ApiDashboardVideoRepository(API_URL);
export const defaultManagementRepo = new ApiVideoManagementRepository(API_URL);
export const defaultPlaylistRepo = new ApiPlaylistRepository(API_URL);

// ─── Types ────────────────────────────────────────────────────────────────────

export interface DashboardPageProps {
  /** Injected in tests; defaults to the real API-backed implementations. */
  dashboardRepo?: DashboardVideoRepository;
  managementRepo?: VideoManagementRepository;
  playlistRepo?: PlaylistRepository;
}

interface EditFormState {
  title: string;
  description: string;
  categoryId: string;
  tags: string; // comma-separated
}

// ─── Helpers ──────────────────────────────────────────────────────────────────

/** Returns Tailwind classes for a status badge pill. */
function statusBadgeClasses(status: DashboardVideo["status"]): string {
  switch (status) {
    case "ready":
      return "bg-green-100 text-green-800";
    case "processing":
      return "bg-yellow-100 text-yellow-800";
    case "pending":
      return "bg-gray-100 text-gray-700";
    case "failed":
      return "bg-red-100 text-red-800";
    default:
      return "bg-gray-100 text-gray-700";
  }
}

function parseTags(raw: string): string[] {
  return raw
    .split(",")
    .map((t) => t.trim())
    .filter(Boolean)
    .filter((t, i, arr) => arr.indexOf(t) === i);
}

// ─── Sub-components ───────────────────────────────────────────────────────────

interface StatusBadgeProps {
  status: DashboardVideo["status"];
}

function StatusBadge({ status }: StatusBadgeProps) {
  return (
    <span
      className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${statusBadgeClasses(status)}`}
    >
      {status}
    </span>
  );
}

interface EditModalProps {
  video: DashboardVideo;
  onClose: () => void;
  onSave: (params: UpdateVideoParams) => Promise<void>;
  saving: boolean;
  error: string | null;
}

function EditModal({ video, onClose, onSave, saving, error }: EditModalProps) {
  const [form, setForm] = useState<EditFormState>({
    title: video.title,
    description: video.description ?? "",
    categoryId: video.categoryId !== null ? String(video.categoryId) : "",
    tags: video.tags.join(", "),
  });

  function handleChange(
    e: React.ChangeEvent<
      HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement
    >
  ) {
    const { name, value } = e.target;
    setForm((prev) => ({ ...prev, [name]: value }));
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    await onSave({
      title: form.title.trim(),
      description: form.description.trim(),
      categoryId: form.categoryId ? parseInt(form.categoryId, 10) : null,
      tags: parseTags(form.tags),
    });
  }

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="edit-modal-title"
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 px-4"
    >
      <div className="w-full max-w-lg bg-white rounded-2xl shadow-xl p-6 space-y-4">
        <h2
          id="edit-modal-title"
          className="text-lg font-semibold text-gray-900"
        >
          Edit video
        </h2>

        {error && (
          <div
            role="alert"
            className="rounded-lg bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-700"
          >
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          {/* Title */}
          <div>
            <label
              htmlFor="edit-title"
              className="block text-sm font-medium text-gray-700 mb-1"
            >
              Title <span className="text-red-500">*</span>
            </label>
            <input
              id="edit-title"
              name="title"
              type="text"
              required
              maxLength={255}
              value={form.title}
              onChange={handleChange}
              disabled={saving}
              className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-50"
            />
          </div>

          {/* Description */}
          <div>
            <label
              htmlFor="edit-description"
              className="block text-sm font-medium text-gray-700 mb-1"
            >
              Description
            </label>
            <textarea
              id="edit-description"
              name="description"
              rows={3}
              value={form.description}
              onChange={handleChange}
              disabled={saving}
              className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-50 resize-none"
            />
          </div>

          {/* Category */}
          <div>
            <label
              htmlFor="edit-categoryId"
              className="block text-sm font-medium text-gray-700 mb-1"
            >
              Category
            </label>
            <select
              id="edit-categoryId"
              name="categoryId"
              value={form.categoryId}
              onChange={handleChange}
              disabled={saving}
              className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-50 bg-white"
            >
              <option value="">— Select a category —</option>
              {CATEGORIES.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.label}
                </option>
              ))}
            </select>
          </div>

          {/* Tags */}
          <div>
            <label
              htmlFor="edit-tags"
              className="block text-sm font-medium text-gray-700 mb-1"
            >
              Tags
            </label>
            <input
              id="edit-tags"
              name="tags"
              type="text"
              value={form.tags}
              onChange={handleChange}
              disabled={saving}
              placeholder="golang, tutorial, programming"
              className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-50"
            />
            <p className="mt-1 text-xs text-gray-400">Separate tags with commas</p>
          </div>

          {/* Actions */}
          <div className="flex justify-end gap-3 pt-2">
            <button
              type="button"
              onClick={onClose}
              disabled={saving}
              className="rounded-lg border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 disabled:opacity-50"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={saving}
              className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-semibold text-white hover:bg-blue-700 disabled:opacity-50"
            >
              {saving ? "Saving…" : "Save changes"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

// ─── Component ────────────────────────────────────────────────────────────────

export function DashboardContent({
  dashboardRepo = defaultDashboardRepo,
  managementRepo = defaultManagementRepo,
  playlistRepo = defaultPlaylistRepo,
}: DashboardPageProps) {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { user, loading, getIdToken } = useAuth();

  // Active tab: "videos" | "playlists"
  const [activeTab, setActiveTab] = useState<"videos" | "playlists">("videos");

  const [videos, setVideos] = useState<DashboardVideo[]>([]);
  const [fetchError, setFetchError] = useState<string | null>(null);
  const [fetching, setFetching] = useState(true);

  // Edit modal state
  const [editingVideo, setEditingVideo] = useState<DashboardVideo | null>(null);
  const [editError, setEditError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  // Delete confirmation state
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [deleteError, setDeleteError] = useState<string | null>(null);

  // Returning from upload — show a "processing" banner for the new video.
  const uploadedId = searchParams.get("uploaded");

  // ─── Playlist state ─────────────────────────────────────────────────────────
  const [playlists, setPlaylists] = useState<PlaylistSummary[]>([]);
  const [playlistsLoading, setPlaylistsLoading] = useState(false);
  const [playlistsLoaded, setPlaylistsLoaded] = useState(false);
  const [playlistsError, setPlaylistsError] = useState<string | null>(null);
  const [newPlaylistTitle, setNewPlaylistTitle] = useState("");
  const [creatingPlaylist, setCreatingPlaylist] = useState(false);
  const [renamingPlaylistId, setRenamingPlaylistId] = useState<string | null>(null);
  const [renameTitle, setRenameTitle] = useState("");
  const [renamingLoading, setRenamingLoading] = useState(false);
  const [deletingPlaylistId, setDeletingPlaylistId] = useState<string | null>(null);
  const [playlistDeleteError, setPlaylistDeleteError] = useState<string | null>(null);

  // Auth guard: return null during loading to prevent flash.
  useEffect(() => {
    if (!loading && !user) {
      router.replace("/login");
    }
  }, [user, loading, router]);

  const fetchVideos = useCallback(async () => {
    const token = await getIdToken();
    if (!token) return;
    setFetching(true);
    setFetchError(null);
    try {
      const data = await dashboardRepo.listMyVideos(token);
      setVideos(data);
    } catch (err: unknown) {
      setFetchError(
        err instanceof Error ? err.message : "Failed to load videos."
      );
    } finally {
      setFetching(false);
    }
  }, [dashboardRepo, getIdToken]);

  const fetchPlaylists = useCallback(async () => {
    const token = await getIdToken();
    if (!token) return;
    setPlaylistsLoading(true);
    setPlaylistsError(null);
    try {
      const data = await playlistRepo.listMine(token);
      setPlaylists(data);
    } catch (err: unknown) {
      setPlaylistsError(
        err instanceof Error ? err.message : "Failed to load playlists."
      );
    } finally {
      setPlaylistsLoading(false);
    }
  }, [playlistRepo, getIdToken]);

  useEffect(() => {
    if (user && !loading) {
      fetchVideos();
    }
  }, [user, loading, fetchVideos]);

  // Lazy-load playlists — only on first activation of the "My playlists" tab.
  useEffect(() => {
    if (activeTab !== "playlists" || playlistsLoaded || !user || loading) return;
    setPlaylistsLoaded(true);
    fetchPlaylists();
  }, [activeTab, playlistsLoaded, user, loading, fetchPlaylists]);

  // Return null during auth loading to prevent flash.
  if (loading) {
    return null;
  }

  if (!user) {
    return null;
  }

  // ─── Handlers ──────────────────────────────────────────────────────────────

  function handleEditClick(video: DashboardVideo) {
    setEditingVideo(video);
    setEditError(null);
  }

  function handleEditClose() {
    setEditingVideo(null);
    setEditError(null);
  }

  async function handleSave(params: UpdateVideoParams) {
    if (!editingVideo) return;
    const token = await getIdToken();
    if (!token) {
      setEditError("You are not authenticated. Please sign in again.");
      return;
    }
    setSaving(true);
    setEditError(null);
    try {
      const updated = await managementRepo.updateVideo(
        editingVideo.id,
        params,
        token
      );
      setVideos((prev) =>
        prev.map((v) =>
          v.id === updated.id
            ? {
                ...v,
                title: updated.title,
                status: updated.status as DashboardVideo["status"],
                thumbnailUrl: updated.thumbnailUrl,
                description: updated.description,
                tags: updated.tags,
              }
            : v
        )
      );
      setEditingVideo(null);
    } catch (err: unknown) {
      setEditError(
        err instanceof Error ? err.message : "Failed to save changes."
      );
    } finally {
      setSaving(false);
    }
  }

  function handleDeleteClick(videoId: string) {
    setDeletingId(videoId);
    setDeleteError(null);
  }

  function handleDeleteCancel() {
    setDeletingId(null);
    setDeleteError(null);
  }

  async function handleDeleteConfirm() {
    if (!deletingId) return;
    const token = await getIdToken();
    if (!token) {
      setDeleteError("You are not authenticated. Please sign in again.");
      return;
    }
    try {
      await managementRepo.deleteVideo(deletingId, token);
      setVideos((prev) => prev.filter((v) => v.id !== deletingId));
      setDeletingId(null);
    } catch (err: unknown) {
      setDeleteError(
        err instanceof Error ? err.message : "Failed to delete video."
      );
    }
  }

  // ─── Playlist handlers ──────────────────────────────────────────────────────

  async function handleCreatePlaylist() {
    const title = newPlaylistTitle.trim();
    if (!title) return;
    const token = await getIdToken();
    if (!token) return;
    setCreatingPlaylist(true);
    setPlaylistsError(null);
    try {
      const created = await playlistRepo.create(title, token);
      setPlaylists((prev) => [created, ...prev]);
      setNewPlaylistTitle("");
    } catch (err: unknown) {
      setPlaylistsError(err instanceof Error ? err.message : "Failed to create playlist.");
    } finally {
      setCreatingPlaylist(false);
    }
  }

  function handleRenameClick(pl: PlaylistSummary) {
    setRenamingPlaylistId(pl.id);
    setRenameTitle(pl.title);
  }

  async function handleRenameConfirm() {
    if (!renamingPlaylistId) return;
    const title = renameTitle.trim();
    if (!title) return;
    const token = await getIdToken();
    if (!token) return;
    setRenamingLoading(true);
    setPlaylistsError(null);
    try {
      const updated = await playlistRepo.updateTitle(renamingPlaylistId, title, token);
      setPlaylists((prev) =>
        prev.map((p) => (p.id === updated.id ? updated : p))
      );
      setRenamingPlaylistId(null);
    } catch (err: unknown) {
      setPlaylistsError(err instanceof Error ? err.message : "Failed to rename playlist.");
    } finally {
      setRenamingLoading(false);
    }
  }

  async function handleDeletePlaylistConfirm() {
    if (!deletingPlaylistId) return;
    const token = await getIdToken();
    if (!token) return;
    setPlaylistDeleteError(null);
    try {
      await playlistRepo.deletePlaylist(deletingPlaylistId, token);
      setPlaylists((prev) => prev.filter((p) => p.id !== deletingPlaylistId));
      setDeletingPlaylistId(null);
    } catch (err: unknown) {
      setPlaylistDeleteError(err instanceof Error ? err.message : "Failed to delete playlist.");
    }
  }

  // ─── Render ────────────────────────────────────────────────────────────────

  return (
    <div className="min-h-screen bg-gray-50 py-10 px-4">
      <div className="max-w-5xl mx-auto space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <h1 className="text-2xl font-bold text-gray-900">My studio</h1>
          <Link
            href="/upload"
            className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-semibold text-white hover:bg-blue-700 transition-colors"
          >
            Upload new video
          </Link>
        </div>

        {/* Tabs */}
        <div className="border-b border-gray-200">
          <nav className="-mb-px flex gap-6">
            <button
              onClick={() => setActiveTab("videos")}
              className={`pb-2 text-sm font-medium border-b-2 transition-colors ${
                activeTab === "videos"
                  ? "border-blue-600 text-blue-600"
                  : "border-transparent text-gray-500 hover:text-gray-700"
              }`}
            >
              My videos
            </button>
            <button
              onClick={() => setActiveTab("playlists")}
              className={`pb-2 text-sm font-medium border-b-2 transition-colors ${
                activeTab === "playlists"
                  ? "border-blue-600 text-blue-600"
                  : "border-transparent text-gray-500 hover:text-gray-700"
              }`}
            >
              My playlists
            </button>
          </nav>
        </div>

        {/* Videos tab content */}
        {activeTab === "videos" && (
          <>
            {/* Upload success banner */}
            {uploadedId && (
              <div
                role="status"
                className="rounded-lg bg-blue-50 border border-blue-200 px-4 py-3 text-sm text-blue-700"
              >
                Your video is being processed. It will appear as{" "}
                <strong>ready</strong> once transcoding is complete.
              </div>
            )}

            {/* Fetch error */}
            {fetchError && (
              <div
                role="alert"
                className="rounded-lg bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-700"
              >
                {fetchError}
              </div>
            )}

            {/* Delete error */}
            {deleteError && (
              <div
                role="alert"
                className="rounded-lg bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-700"
              >
                {deleteError}
              </div>
            )}

            {/* Loading / empty / table */}
            {fetching ? (
              <p className="text-gray-500">Loading your videos…</p>
            ) : videos.length === 0 ? (
              <div className="rounded-2xl bg-white shadow-sm p-8 text-center">
                <p className="text-gray-500 mb-4">You haven&apos;t uploaded any videos yet.</p>
                <Link
                  href="/upload"
                  className="inline-block rounded-lg bg-blue-600 px-4 py-2 text-sm font-semibold text-white hover:bg-blue-700"
                >
                  Upload your first video
                </Link>
              </div>
            ) : (
              <div className="rounded-2xl bg-white shadow-sm overflow-hidden">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-gray-100 text-left">
                      <th className="px-4 py-3 font-medium text-gray-500 w-16">Thumb</th>
                      <th className="px-4 py-3 font-medium text-gray-500">Title</th>
                      <th className="px-4 py-3 font-medium text-gray-500">Status</th>
                      <th className="px-4 py-3 font-medium text-gray-500 text-right">Views</th>
                      <th className="px-4 py-3 font-medium text-gray-500">Date</th>
                      <th className="px-4 py-3 font-medium text-gray-500 text-right">Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {videos.map((video) => (
                      <tr
                        key={video.id}
                        className="border-b border-gray-50 last:border-0 hover:bg-gray-50 transition-colors"
                      >
                        {/* Thumbnail */}
                        <td className="px-4 py-3">
                          {video.thumbnailUrl ? (
                            // eslint-disable-next-line @next/next/no-img-element
                            <img
                              src={video.thumbnailUrl}
                              alt={`${video.title} thumbnail`}
                              className="w-14 h-9 object-cover rounded"
                            />
                          ) : (
                            <div className="w-14 h-9 bg-gray-100 rounded flex items-center justify-center text-gray-400 text-xs">
                              —
                            </div>
                          )}
                        </td>

                        {/* Title */}
                        <td className="px-4 py-3 font-medium text-gray-900 max-w-xs truncate">
                          {video.status === "ready" ? (
                            <Link
                              href={`/v/${video.id}`}
                              className="hover:text-blue-600 transition-colors"
                            >
                              {video.title}
                            </Link>
                          ) : (
                            video.title
                          )}
                        </td>

                        {/* Status badge */}
                        <td className="px-4 py-3">
                          <StatusBadge status={video.status} />
                        </td>

                        {/* View count */}
                        <td className="px-4 py-3 text-right text-gray-500">
                          {video.viewCount.toLocaleString()}
                        </td>

                        {/* Created date */}
                        <td className="px-4 py-3 text-gray-500 whitespace-nowrap">
                          {new Date(video.createdAt).toLocaleDateString()}
                        </td>

                        {/* Actions */}
                        <td className="px-4 py-3 text-right whitespace-nowrap">
                          <button
                            onClick={() => handleEditClick(video)}
                            className="text-blue-600 hover:text-blue-800 font-medium mr-3"
                            aria-label={`Edit ${video.title}`}
                          >
                            Edit
                          </button>
                          {deletingId === video.id ? (
                            <span className="inline-flex gap-2">
                              <button
                                onClick={handleDeleteConfirm}
                                className="text-red-600 hover:text-red-800 font-medium"
                              >
                                Confirm
                              </button>
                              <button
                                onClick={handleDeleteCancel}
                                className="text-gray-500 hover:text-gray-700 font-medium"
                              >
                                Cancel
                              </button>
                            </span>
                          ) : (
                            <button
                              onClick={() => handleDeleteClick(video.id)}
                              className="text-red-600 hover:text-red-800 font-medium"
                              aria-label={`Delete ${video.title}`}
                            >
                              Delete
                            </button>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </>
        )}

        {/* Playlists tab content */}
        {activeTab === "playlists" && (
          <>
            {/* Error */}
            {playlistsError && (
              <div role="alert" className="rounded-lg bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-700">
                {playlistsError}
              </div>
            )}
            {playlistDeleteError && (
              <div role="alert" className="rounded-lg bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-700">
                {playlistDeleteError}
              </div>
            )}

            {/* Create new playlist */}
            <div className="flex gap-2 items-center">
              <input
                type="text"
                value={newPlaylistTitle}
                onChange={(e) => setNewPlaylistTitle(e.target.value)}
                placeholder="New playlist title"
                maxLength={255}
                className="flex-1 rounded-lg border border-gray-300 px-3 py-2 text-sm shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                onKeyDown={(e) => {
                  if (e.key === "Enter") handleCreatePlaylist();
                }}
              />
              <button
                onClick={handleCreatePlaylist}
                disabled={creatingPlaylist || !newPlaylistTitle.trim()}
                className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-semibold text-white hover:bg-blue-700 disabled:opacity-50"
              >
                {creatingPlaylist ? "Creating…" : "Create playlist"}
              </button>
            </div>

            {/* Playlist list */}
            {playlistsLoading ? (
              <p className="text-gray-500">Loading your playlists…</p>
            ) : playlists.length === 0 ? (
              <div className="rounded-2xl bg-white shadow-sm p-8 text-center">
                <p className="text-gray-500">You don&apos;t have any playlists yet.</p>
              </div>
            ) : (
              <div className="rounded-2xl bg-white shadow-sm overflow-hidden">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-gray-100 text-left">
                      <th className="px-4 py-3 font-medium text-gray-500">Title</th>
                      <th className="px-4 py-3 font-medium text-gray-500">Date</th>
                      <th className="px-4 py-3 font-medium text-gray-500 text-right">Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {playlists.map((pl) => (
                      <tr key={pl.id} className="border-b border-gray-50 last:border-0 hover:bg-gray-50 transition-colors">
                        <td className="px-4 py-3 font-medium text-gray-900">
                          {renamingPlaylistId === pl.id ? (
                            <span className="flex items-center gap-2">
                              <input
                                type="text"
                                value={renameTitle}
                                onChange={(e) => setRenameTitle(e.target.value)}
                                maxLength={255}
                                className="rounded border border-gray-300 px-2 py-1 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                                onKeyDown={(e) => {
                                  if (e.key === "Enter") handleRenameConfirm();
                                  if (e.key === "Escape") setRenamingPlaylistId(null);
                                }}
                              />
                              <button
                                onClick={handleRenameConfirm}
                                disabled={renamingLoading || !renameTitle.trim()}
                                className="text-blue-600 hover:text-blue-800 font-medium disabled:opacity-50"
                              >
                                {renamingLoading ? "Saving…" : "Save"}
                              </button>
                              <button
                                onClick={() => setRenamingPlaylistId(null)}
                                className="text-gray-500 hover:text-gray-700 font-medium"
                              >
                                Cancel
                              </button>
                            </span>
                          ) : (
                            <Link href={`/pl/${pl.id}`} className="hover:text-blue-600 transition-colors">
                              {pl.title}
                            </Link>
                          )}
                        </td>
                        <td className="px-4 py-3 text-gray-500 whitespace-nowrap">
                          {new Date(pl.createdAt).toLocaleDateString()}
                        </td>
                        <td className="px-4 py-3 text-right whitespace-nowrap">
                          <button
                            onClick={() => handleRenameClick(pl)}
                            className="text-blue-600 hover:text-blue-800 font-medium mr-3"
                            aria-label={`Rename ${pl.title}`}
                          >
                            Rename
                          </button>
                          {deletingPlaylistId === pl.id ? (
                            <span className="inline-flex gap-2">
                              <button
                                onClick={handleDeletePlaylistConfirm}
                                className="text-red-600 hover:text-red-800 font-medium"
                              >
                                Confirm
                              </button>
                              <button
                                onClick={() => setDeletingPlaylistId(null)}
                                className="text-gray-500 hover:text-gray-700 font-medium"
                              >
                                Cancel
                              </button>
                            </span>
                          ) : (
                            <button
                              onClick={() => {
                                setDeletingPlaylistId(pl.id);
                                setPlaylistDeleteError(null);
                              }}
                              className="text-red-600 hover:text-red-800 font-medium"
                              aria-label={`Delete ${pl.title}`}
                            >
                              Delete
                            </button>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </>
        )}
      </div>

      {/* Edit modal (videos tab) */}
      {editingVideo && (
        <EditModal
          video={editingVideo}
          onClose={handleEditClose}
          onSave={handleSave}
          saving={saving}
          error={editError}
        />
      )}
    </div>
  );
}
