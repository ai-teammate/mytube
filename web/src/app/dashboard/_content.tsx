"use client";

import { useState, useEffect, useCallback, useMemo } from "react";
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
import DashboardVideoCard from "@/components/DashboardVideoCard";
import VideoCardSkeleton from "@/components/VideoCardSkeleton";
import styles from "./_content.module.css";

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

function parseTags(raw: string): string[] {
  return raw
    .split(",")
    .map((t) => t.trim())
    .filter(Boolean)
    .filter((t, i, arr) => arr.indexOf(t) === i);
}

// ─── Sub-components ───────────────────────────────────────────────────────────

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
      className={styles.modalOverlay}
    >
      <div className={styles.modalCard}>
        <h2
          id="edit-modal-title"
          className={styles.modalTitle}
        >
          Edit video
        </h2>

        {error && (
          <div
            role="alert"
            className={styles.bannerError}
          >
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          {/* Title */}
          <div>
            <label
              htmlFor="edit-title"
              className={styles.formLabel}
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
              className={styles.formInput}
            />
          </div>

          {/* Description */}
          <div>
            <label
              htmlFor="edit-description"
              className={styles.formLabel}
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
              className={styles.formInputResize}
            />
          </div>

          {/* Category */}
          <div>
            <label
              htmlFor="edit-categoryId"
              className={styles.formLabel}
            >
              Category
            </label>
            <select
              id="edit-categoryId"
              name="categoryId"
              value={form.categoryId}
              onChange={handleChange}
              disabled={saving}
              className={styles.formInput}
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
              className={styles.formLabel}
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
              className={styles.formInput}
            />
            <p className={styles.formHint}>Separate tags with commas</p>
          </div>

          {/* Actions */}
          <div className={styles.modalActions}>
            <button
              type="button"
              onClick={onClose}
              disabled={saving}
              className={styles.btnSecondary}
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={saving}
              className={styles.btnCta}
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
  const [deleting, setDeleting] = useState(false);

  // Returning from upload — show a "processing" banner for the new video.
  const uploadedId = searchParams.get("uploaded");

  // ─── Toolbar filter state ────────────────────────────────────────────────────
  const [searchQuery, setSearchQuery] = useState("");
  const [categoryFilter, setCategoryFilter] = useState("");
  const [activePlaylistId, setActivePlaylistId] = useState<string | null>(null);
  /** videoId → array of playlist IDs it belongs to; built via parallel getByID calls. */
  const [videoPlaylistMap, setVideoPlaylistMap] = useState<Record<string, string[]>>({});

  // ─── Playlist state ─────────────────────────────────────────────────────────
  const [playlists, setPlaylists] = useState<PlaylistSummary[]>([]);
  const [playlistsLoading, setPlaylistsLoading] = useState(false);
  const [playlistsError, setPlaylistsError] = useState<string | null>(null);
  const [newPlaylistTitle, setNewPlaylistTitle] = useState("");
  const [creatingPlaylist, setCreatingPlaylist] = useState(false);
  const [renamingPlaylistId, setRenamingPlaylistId] = useState<string | null>(null);
  const [renameTitle, setRenameTitle] = useState("");
  const [renamingLoading, setRenamingLoading] = useState(false);
  const [deletingPlaylistId, setDeletingPlaylistId] = useState<string | null>(null);
  const [playlistDeleteError, setPlaylistDeleteError] = useState<string | null>(null);
  const [deletingPlaylist, setDeletingPlaylist] = useState(false);

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
      // Build video→playlist map in parallel for chip filtering (Option A).
      if (data.length > 0) {
        const details = await Promise.all(
          data.map((pl) => playlistRepo.getByID(pl.id).catch(() => null))
        );
        const map: Record<string, string[]> = {};
        for (const detail of details) {
          if (!detail) continue;
          for (const video of detail.videos) {
            if (!map[video.id]) map[video.id] = [];
            map[video.id].push(detail.id);
          }
        }
        setVideoPlaylistMap(map);
      }
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
      fetchPlaylists();
    }
  }, [user, loading, fetchVideos, fetchPlaylists]);

  // ─── Derived state — must be before any early return ─────────────────────
  const filteredVideos = useMemo(() => {
    let result = videos;
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      result = result.filter((v) => v.title.toLowerCase().includes(q));
    }
    if (categoryFilter) {
      result = result.filter((v) => String(v.categoryId) === categoryFilter);
    }
    if (activePlaylistId) {
      result = result.filter((v) =>
        (videoPlaylistMap[v.id] ?? []).includes(activePlaylistId)
      );
    }
    return result;
  }, [videos, searchQuery, categoryFilter, activePlaylistId, videoPlaylistMap]);

  // Return null during auth loading to prevent flash.
  if (loading) {
    return null;
  }

  if (!user) {
    return null;
  }

  // ─── Handlers ──────────────────────────────────────────────────────────────

  function handleResetFilters() {
    setSearchQuery("");
    setCategoryFilter("");
    setActivePlaylistId(null);
  }

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
    const videoIdToDelete = deletingId;
    const token = await getIdToken();
    if (!token) {
      setDeleteError("You are not authenticated. Please sign in again.");
      return;
    }
    setDeleting(true);
    setDeleteError(null);
    try {
      await managementRepo.deleteVideo(videoIdToDelete, token);
      // After successful deletion, filter out the video and reset state
      setVideos((prev) => prev.filter((v) => v.id !== videoIdToDelete));
    } catch (err: unknown) {
      setDeleteError(
        err instanceof Error ? err.message : "Failed to delete video."
      );
    } finally {
      setDeletingId(null);
      setDeleting(false);
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
    const playlistIdToDelete = deletingPlaylistId;
    const token = await getIdToken();
    if (!token) return;
    setDeletingPlaylist(true);
    setPlaylistDeleteError(null);
    try {
      await playlistRepo.deletePlaylist(playlistIdToDelete, token);
      setPlaylists((prev) => prev.filter((p) => p.id !== playlistIdToDelete));
    } catch (err: unknown) {
      setPlaylistDeleteError(err instanceof Error ? err.message : "Failed to delete playlist.");
    } finally {
      setDeletingPlaylistId(null);
      setDeletingPlaylist(false);
    }
  }

  // ─── Render ────────────────────────────────────────────────────────────────

  return (
    <div className={styles.pageWrapper}>
      <div className="max-w-5xl mx-auto space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <h1 className={styles.sectionHeading}>My Videos</h1>
          <Link
            href="/upload"
            className={styles.btnCta}
          >
            Upload new video
          </Link>
        </div>

        {/* Tabs */}
        <div className={styles.tabBar}>
          <nav className={styles.tabNav}>
            <button
              onClick={() => setActiveTab("videos")}
              className={`${styles.tabBtn} ${activeTab === "videos" ? styles.tabBtnActive : ""}`}
            >
              My videos
            </button>
            <button
              onClick={() => setActiveTab("playlists")}
              className={`${styles.tabBtn} ${activeTab === "playlists" ? styles.tabBtnActive : ""}`}
            >
              My playlists
            </button>
          </nav>
        </div>

        {/* Videos tab content */}
        {activeTab === "videos" && (
          <div className={styles.videosSection}>
            {/* Upload success banner */}
            {uploadedId && (
              <div
                role="status"
                className={styles.bannerInfo}
              >
                Your video is being processed. It will appear as{" "}
                <strong>ready</strong> once transcoding is complete.
              </div>
            )}

            {/* Fetch error */}
            {fetchError && (
              <div
                role="alert"
                className={styles.bannerError}
              >
                {fetchError}
              </div>
            )}

            {/* Delete error */}
            {deleteError && (
              <div
                role="alert"
                className={styles.bannerError}
              >
                {deleteError}
              </div>
            )}

            {/* Toolbar card + Playlist chips — only shown when videos exist */}
            {videos.length > 0 && (
              <>
            <div className={styles.toolbar}>
              <div className={styles.toolbarGrid}>
                <input
                  type="search"
                  aria-label="Search videos"
                  placeholder="Search videos…"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className={styles.toolbarInput}
                />
                <select
                  aria-label="Filter by category"
                  value={categoryFilter}
                  onChange={(e) => setCategoryFilter(e.target.value)}
                  className={styles.toolbarSelect}
                >
                  <option value="">All categories</option>
                  {CATEGORIES.map((c) => (
                    <option key={c.id} value={String(c.id)}>
                      {c.label}
                    </option>
                  ))}
                </select>
                <button
                  onClick={handleResetFilters}
                  className={styles.btnReset}
                >
                  Reset filters
                </button>
              </div>
            </div>

            {/* Playlist chips */}
            {playlists.length > 0 && (
              <div className={styles.playlistRow} role="group" aria-label="Filter by playlist">
                <button
                  onClick={() => setActivePlaylistId(null)}
                  className={`${styles.chip} ${!activePlaylistId ? styles.chipActive : styles.chipInactive}`}
                >
                  All
                </button>
                {playlists.map((pl) => (
                  <button
                    key={pl.id}
                    onClick={() =>
                      setActivePlaylistId(
                        activePlaylistId === pl.id ? null : pl.id
                      )
                    }
                    className={`${styles.chip} ${activePlaylistId === pl.id ? styles.chipActive : styles.chipInactive}`}
                  >
                    {pl.title}
                  </button>
                ))}
              </div>
            )}
              </>
            )}

            {/* Loading / empty / grid */}
            {fetching ? (
              <div className={styles.videoGrid}>
                <VideoCardSkeleton count={4} />
              </div>
            ) : filteredVideos.length === 0 ? (
              <div className={styles.emptyState}>
                {videos.length === 0 ? (
                  <>
                    <p className={styles.emptyText}>
                      You haven&apos;t uploaded any videos yet.
                    </p>
                    <Link href="/upload" className={styles.btnUploadCta}>
                      Upload your first video
                    </Link>
                  </>
                ) : (
                  <p className={styles.emptyText}>
                    No videos match your filters.
                  </p>
                )}
              </div>
            ) : (
              <div className={styles.videoGrid}>
                {filteredVideos.map((video) => (
                  <DashboardVideoCard
                    key={video.id}
                    video={video}
                    onEdit={handleEditClick}
                    onDelete={handleDeleteClick}
                    isDeleting={deletingId === video.id && deleting}
                    isConfirmingDelete={deletingId === video.id}
                    onConfirmDelete={handleDeleteConfirm}
                    onCancelDelete={handleDeleteCancel}
                  />
                ))}
              </div>
            )}
          </div>
        )}

        {/* Playlists tab content */}
        {activeTab === "playlists" && (
          <>
            {/* Error */}
            {playlistsError && (
              <div role="alert" className={styles.bannerError}>
                {playlistsError}
              </div>
            )}
            {playlistDeleteError && (
              <div role="alert" className={styles.bannerError}>
                {playlistDeleteError}
              </div>
            )}

            {/* Create new playlist */}
            <div className={styles.createRow}>
              <input
                type="text"
                value={newPlaylistTitle}
                onChange={(e) => setNewPlaylistTitle(e.target.value)}
                placeholder="New playlist title"
                maxLength={255}
                className={styles.createRowInput}
                onKeyDown={(e) => {
                  if (e.key === "Enter") handleCreatePlaylist();
                }}
              />
              <button
                onClick={handleCreatePlaylist}
                disabled={creatingPlaylist || !newPlaylistTitle.trim()}
                className={styles.btnCta}
              >
                {creatingPlaylist ? "Creating…" : "Create playlist"}
              </button>
            </div>

            {/* Playlist list */}
            {playlistsLoading ? (
              <p className={styles.playlistLoading}>Loading your playlists…</p>
            ) : playlists.length === 0 ? (
              <div className={styles.playlistEmpty}>
                <p>You don&apos;t have any playlists yet.</p>
              </div>
            ) : (
              <div className={styles.playlistTable}>
                <table className={styles.playlistTableEl}>
                  <thead className={styles.playlistTableHead}>
                    <tr>
                      <th className={styles.playlistTableHeadCell}>Title</th>
                      <th className={styles.playlistTableHeadCell}>Date</th>
                      <th className={`${styles.playlistTableHeadCell} text-right`}>Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {playlists.map((pl) => (
                      <tr key={pl.id} className={styles.playlistTableRow}>
                        <td className={styles.playlistTableCellTitle}>
                          {renamingPlaylistId === pl.id ? (
                            <span className="flex items-center gap-2">
                              <input
                                type="text"
                                value={renameTitle}
                                onChange={(e) => setRenameTitle(e.target.value)}
                                maxLength={255}
                                className={styles.renameInput}
                                onKeyDown={(e) => {
                                  if (e.key === "Enter") handleRenameConfirm();
                                  if (e.key === "Escape") setRenamingPlaylistId(null);
                                }}
                              />
                              <button
                                onClick={handleRenameConfirm}
                                disabled={renamingLoading || !renameTitle.trim()}
                                className={styles.btnLinkAccent}
                              >
                                {renamingLoading ? "Saving…" : "Save"}
                              </button>
                              <button
                                onClick={() => setRenamingPlaylistId(null)}
                                className={styles.btnLinkMuted}
                              >
                                Cancel
                              </button>
                            </span>
                          ) : (
                            <Link href={`/pl/${pl.id}`} className={styles.playlistLink}>
                              {pl.title}
                            </Link>
                          )}
                        </td>
                        <td className={styles.playlistTableCellDate}>
                          {new Date(pl.createdAt).toLocaleDateString()}
                        </td>
                        <td className={styles.playlistTableCellActions}>
                          <button
                            onClick={() => handleRenameClick(pl)}
                            className={`${styles.btnLinkAccent} mr-3`}
                            aria-label={`Rename ${pl.title}`}
                          >
                            Rename
                          </button>
                          {deletingPlaylistId === pl.id ? (
                            <span className="inline-flex gap-2">
                              <button
                                onClick={() => handleDeletePlaylistConfirm()}
                                disabled={deletingPlaylist}
                                className={styles.btnLinkDanger}
                              >
                                {deletingPlaylist ? "Deleting..." : "Confirm"}
                              </button>
                              <button
                                onClick={() => setDeletingPlaylistId(null)}
                                disabled={deletingPlaylist}
                                className={styles.btnLinkMuted}
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
                              className={styles.btnLinkDanger}
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
