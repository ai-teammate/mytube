"use client";

import { useState, useRef, useEffect, useMemo, ChangeEvent } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/context/AuthContext";
import VideoCard from "@/components/VideoCard";
import { ApiVideoUploadRepository } from "@/data/videoUploadRepository";
import { ApiDashboardVideoRepository } from "@/data/dashboardRepository";
import type { DashboardVideoRepository, DashboardVideo } from "@/domain/dashboard";
import type { VideoCardItem } from "@/domain/search";
import { CATEGORIES } from "@/domain/categories";
import {
  ACCEPTED_VIDEO_MIME_TYPES,
  UPLOAD_SIZE_WARNING_BYTES,
} from "@/domain/videoUpload";
import styles from "./upload.module.css";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "";

const uploadRepo = new ApiVideoUploadRepository(API_URL);
export const defaultLibraryRepo = new ApiDashboardVideoRepository(API_URL);

// ─── Types ────────────────────────────────────────────────────────────────────

interface UploadFormState {
  title: string;
  description: string;
  categoryId: string; // string for select value; "" means no category
  tags: string; // comma-separated
}

type UploadPhase = "idle" | "uploading" | "done" | "error";

export interface UploadPageContentProps {
  /** Injected in tests; defaults to the real API-backed implementation. */
  libraryRepo?: DashboardVideoRepository;
}

// ─── Helpers ──────────────────────────────────────────────────────────────────

function parseTags(raw: string): string[] {
  return raw
    .split(",")
    .map((t) => t.trim())
    .filter(Boolean)
    .filter((t, i, arr) => arr.indexOf(t) === i); // deduplicate
}

function formatBytes(bytes: number): string {
  const gb = bytes / (1024 * 1024 * 1024);
  return `${gb.toFixed(1)} GB`;
}

function dashboardVideoToCardItem(
  video: DashboardVideo,
  uploaderUsername: string
): VideoCardItem {
  return {
    id: video.id,
    title: video.title,
    thumbnailUrl: video.thumbnailUrl,
    viewCount: video.viewCount,
    uploaderUsername,
    createdAt: video.createdAt,
    tags: video.tags,
  };
}

// ─── Component ────────────────────────────────────────────────────────────────

export function UploadPageContent({
  libraryRepo = defaultLibraryRepo,
}: UploadPageContentProps) {
  const router = useRouter();
  const { user, getIdToken } = useAuth();

  // ─── Upload form state ──────────────────────────────────────────────────────

  const [form, setForm] = useState<UploadFormState>({
    title: "",
    description: "",
    categoryId: "",
    tags: "",
  });

  const [file, setFile] = useState<File | null>(null);
  const [fileSizeWarning, setFileSizeWarning] = useState(false);
  const [mimeTypeError, setMimeTypeError] = useState(false);

  const [phase, setPhase] = useState<UploadPhase>("idle");
  const [uploadProgress, setUploadProgress] = useState(0); // 0–100
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const xhrRef = useRef<XMLHttpRequest | null>(null);

  // ─── Library state ──────────────────────────────────────────────────────────

  const [rawVideos, setRawVideos] = useState<DashboardVideo[]>([]);
  const [libLoading, setLibLoading] = useState(false);
  const [libError, setLibError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [filterCategory, setFilterCategory] = useState("");
  const [sortOrder, setSortOrder] = useState<"newest" | "oldest">("newest");

  // Derive uploader username from auth user (matches API convention: email prefix)
  const uploaderUsername =
    user?.email?.split("@")[0] ?? user?.displayName ?? "";

  // ─── Load library on mount ──────────────────────────────────────────────────

  useEffect(() => {
    let cancelled = false;

    async function loadLibrary() {
      setLibLoading(true);
      setLibError(null);
      try {
        const token = await getIdToken();
        if (!token || cancelled) return;
        const videos = await libraryRepo.listMyVideos(token);
        if (!cancelled) {
          setRawVideos(videos);
        }
      } catch (err) {
        if (!cancelled) {
          setLibError(
            err instanceof Error ? err.message : "Failed to load videos."
          );
        }
      } finally {
        if (!cancelled) {
          setLibLoading(false);
        }
      }
    }

    loadLibrary();
    return () => {
      cancelled = true;
    };
  }, [libraryRepo, getIdToken]);

  // ─── Client-side filter + sort ──────────────────────────────────────────────

  const filteredVideos = useMemo(() => {
    let result = rawVideos;

    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      result = result.filter(
        (v) =>
          v.title.toLowerCase().includes(q) ||
          v.tags.some((t) => t.toLowerCase().includes(q))
      );
    }

    if (filterCategory) {
      const catId = parseInt(filterCategory, 10);
      result = result.filter((v) => v.categoryId === catId);
    }

    const sorted =
      sortOrder === "newest"
        ? [...result].sort((a, b) => b.createdAt.localeCompare(a.createdAt))
        : [...result].sort((a, b) => a.createdAt.localeCompare(b.createdAt));

    return sorted.map((v) => dashboardVideoToCardItem(v, uploaderUsername));
  }, [rawVideos, searchQuery, filterCategory, sortOrder, uploaderUsername]);

  // ─── Upload handlers ────────────────────────────────────────────────────────

  function handleFormChange(
    e: ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>
  ) {
    const { name, value } = e.target;
    setForm((prev) => ({ ...prev, [name]: value }));
  }

  function handleFileChange(e: ChangeEvent<HTMLInputElement>) {
    setFileSizeWarning(false);
    setMimeTypeError(false);

    const selected = e.target.files?.[0] ?? null;
    if (!selected) {
      setFile(null);
      return;
    }

    const mimeOk = (ACCEPTED_VIDEO_MIME_TYPES as readonly string[]).includes(
      selected.type
    );
    if (!mimeOk) {
      setMimeTypeError(true);
      setFile(null);
      return;
    }

    if (selected.size > UPLOAD_SIZE_WARNING_BYTES) {
      setFileSizeWarning(true);
    }

    setFile(selected);
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setErrorMessage(null);

    if (!file) {
      setErrorMessage("Please select a video file.");
      return;
    }

    const token = await getIdToken();
    if (!token) {
      setErrorMessage("You are not authenticated. Please sign in again.");
      return;
    }

    setPhase("uploading");
    setUploadProgress(0);

    let videoId: string;
    let uploadUrl: string;

    try {
      const result = await uploadRepo.initiateUpload(
        {
          title: form.title.trim(),
          description: form.description.trim(),
          categoryId: form.categoryId ? parseInt(form.categoryId, 10) : null,
          tags: parseTags(form.tags),
          file,
        },
        token
      );
      videoId = result.videoId;
      uploadUrl = result.uploadUrl;
    } catch (err: unknown) {
      const msg =
        err instanceof Error ? err.message : "Failed to initiate upload.";
      setErrorMessage(msg);
      setPhase("error");
      return;
    }

    // Upload the file directly to GCS via the signed URL using XHR (supports
    // onprogress for a real-time progress bar).
    let uploadFailed = false;

    await new Promise<void>((resolve, reject) => {
      const xhr = new XMLHttpRequest();
      xhrRef.current = xhr;

      xhr.upload.onprogress = (event) => {
        if (event.lengthComputable) {
          setUploadProgress(Math.round((event.loaded / event.total) * 100));
        }
      };

      xhr.onload = () => {
        if (xhr.status >= 200 && xhr.status < 300) {
          setUploadProgress(100);
          resolve();
        } else {
          reject(new Error(`GCS upload failed with status ${xhr.status}`));
        }
      };

      xhr.onerror = () => reject(new Error("Network error during upload."));

      xhr.open("PUT", uploadUrl);
      xhr.setRequestHeader("Content-Type", file.type);
      xhr.send(file);
    }).catch((err: unknown) => {
      uploadFailed = true;
      const msg = err instanceof Error ? err.message : "Upload failed.";
      setErrorMessage(msg);
      setPhase("error");
    });

    if (!uploadFailed) {
      setPhase("done");
      // After successful GCS upload, verify the session is still valid before
      // redirecting. If the session expired during the upload, redirect to login.
      const newToken = await getIdToken();
      if (!newToken) {
        router.replace("/login");
        return;
      }
      router.replace(`/dashboard?uploaded=${videoId}`);
    }
  }

  // ─── Library toolbar handlers ───────────────────────────────────────────────

  function handleReset() {
    setSearchQuery("");
    setFilterCategory("");
  }

  function toggleSort() {
    setSortOrder((prev) => (prev === "newest" ? "oldest" : "newest"));
  }

  // ─── Render ────────────────────────────────────────────────────────────────

  return (
    <div className={styles.workspace}>
      {/* ── Left column: upload card ── */}
      <section className={styles.uploadCard}>
        <h2 className={styles.cardHeading}>Personal Video Upload</h2>

        {errorMessage && (
          <div role="alert" className={styles.errorAlert}>
            {errorMessage}
          </div>
        )}

        {fileSizeWarning && (
          <div role="note" className={styles.warningNote}>
            Warning: file is larger than {formatBytes(UPLOAD_SIZE_WARNING_BYTES)}.
            Uploads may take a long time on slow connections.
          </div>
        )}

        {mimeTypeError && (
          <div role="alert" className={styles.errorAlert}>
            Unsupported file type. Please select an MP4, MOV, AVI, or WebM
            video file.
          </div>
        )}

        <form onSubmit={handleSubmit} className={styles.form}>
          {/* File picker */}
          <div className={styles.field}>
            <label htmlFor="video-file" className={styles.fieldLabel}>
              Video file{" "}
              <span className="text-red-500" aria-hidden="true">
                *
              </span>
            </label>
            <input
              id="video-file"
              type="file"
              accept={ACCEPTED_VIDEO_MIME_TYPES.map((t) => t).join(",")}
              onChange={handleFileChange}
              disabled={phase === "uploading"}
              className={styles.fileInput}
            />
            {file && (
              <p className={styles.tiny}>
                {file.name} ({(file.size / (1024 * 1024)).toFixed(1)} MB)
              </p>
            )}
            <p className={styles.tiny}>
              Supported formats: MP4, MOV, AVI, WebM
            </p>
          </div>

          {/* Title */}
          <div className={styles.field}>
            <label htmlFor="title" className={styles.fieldLabel}>
              Title{" "}
              <span className="text-red-500" aria-hidden="true">
                *
              </span>
            </label>
            <input
              id="title"
              name="title"
              type="text"
              required
              maxLength={255}
              value={form.title}
              onChange={handleFormChange}
              disabled={phase === "uploading"}
              placeholder="Enter video title"
              className={styles.formControl}
            />
          </div>

          {/* Description */}
          <div className={styles.field}>
            <label htmlFor="description" className={styles.fieldLabel}>
              Description
            </label>
            <textarea
              id="description"
              name="description"
              rows={3}
              value={form.description}
              onChange={handleFormChange}
              disabled={phase === "uploading"}
              placeholder="Optional: describe your video"
              className={`${styles.formControl} ${styles.textareaModifier}`}
            />
          </div>

          {/* Category */}
          <div className={styles.field}>
            <label htmlFor="categoryId" className={styles.fieldLabel}>
              Category
            </label>
            <select
              id="categoryId"
              name="categoryId"
              value={form.categoryId}
              onChange={handleFormChange}
              disabled={phase === "uploading"}
              className={styles.selectControl}
            >
              {/* Category IDs match seeds in api/migrations/0002_seed_categories.up.sql */}
              <option value="">— Select a category —</option>
              {CATEGORIES.map((cat) => (
                <option key={cat.id} value={String(cat.id)}>
                  {cat.label}
                </option>
              ))}
            </select>
          </div>

          {/* Tags */}
          <div className={styles.field}>
            <label htmlFor="tags" className={styles.fieldLabel}>
              Tags
            </label>
            <input
              id="tags"
              name="tags"
              type="text"
              value={form.tags}
              onChange={handleFormChange}
              disabled={phase === "uploading"}
              placeholder="golang, tutorial, programming"
              className={styles.formControl}
            />
            <p className={styles.tiny}>Separate tags with commas</p>
          </div>

          {/* Progress bar — rendered only while uploading (Option B: clean idle state) */}
          {phase === "uploading" && (
            <div>
              <div className={styles.progressLabel}>
                <span>Uploading…</span>
                <span>{uploadProgress}%</span>
              </div>
              <div
                className={styles.progressShell}
                aria-label="upload progress"
              >
                <div
                  role="progressbar"
                  aria-valuenow={uploadProgress}
                  aria-valuemin={0}
                  aria-valuemax={100}
                  className={styles.progressFill}
                  style={{ width: `${uploadProgress}%` }}
                />
              </div>
            </div>
          )}

          {/* Submit */}
          <button
            type="submit"
            disabled={phase === "uploading" || phase === "done"}
            className={styles.btnCta}
          >
            {phase === "uploading" ? "Uploading…" : "Upload video"}
          </button>
        </form>
      </section>

      {/* ── Right column: library area ── */}
      <section className={styles.libraryArea}>
        {/* Toolbar */}
        <div className={styles.toolbarCard}>
          <div className={styles.toolbarRow}>
            <input
              type="search"
              placeholder="Search your videos…"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              aria-label="search videos"
              className={styles.toolbarInput}
            />
            <select
              value={filterCategory}
              onChange={(e) => setFilterCategory(e.target.value)}
              aria-label="filter by category"
              className={styles.toolbarSelect}
            >
              <option value="">All categories</option>
              {CATEGORIES.map((cat) => (
                <option key={cat.id} value={String(cat.id)}>
                  {cat.label}
                </option>
              ))}
            </select>
            <button
              type="button"
              onClick={handleReset}
              className={styles.toolbarReset}
            >
              Reset
            </button>
          </div>
        </div>

        {/* Section heading */}
        <div className={styles.sectionHeadingRow}>
          <h3 className={styles.sectionTitle}>Recently Uploaded</h3>
          <button
            type="button"
            onClick={toggleSort}
            className={styles.sortLink}
          >
            {sortOrder === "newest" ? "Newest first ↓" : "Oldest first ↑"}
          </button>
        </div>

        {/* Library content */}
        {libLoading && (
          <p className={styles.libraryMessage} aria-live="polite">
            Loading videos…
          </p>
        )}

        {libError && !libLoading && (
          <p role="alert" className={styles.libraryError}>
            {libError}
          </p>
        )}

        {!libLoading && !libError && filteredVideos.length === 0 && (
          <p className={styles.libraryMessage}>
            {searchQuery || filterCategory
              ? "No videos match your filters."
              : "No videos yet. Upload your first video!"}
          </p>
        )}

        {!libLoading && !libError && filteredVideos.length > 0 && (
          <div className={styles.videoGrid} aria-label="video library">
            {filteredVideos.map((video) => (
              <VideoCard key={video.id} video={video} />
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
