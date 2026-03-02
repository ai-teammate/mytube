"use client";

import { useState, useEffect, useRef, ChangeEvent } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/context/AuthContext";
import { ApiVideoUploadRepository } from "@/data/videoUploadRepository";
import {
  ACCEPTED_VIDEO_MIME_TYPES,
  UPLOAD_SIZE_WARNING_BYTES,
} from "@/domain/videoUpload";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "";

const uploadRepo = new ApiVideoUploadRepository(API_URL);

// ─── Types ────────────────────────────────────────────────────────────────────

interface UploadFormState {
  title: string;
  description: string;
  categoryId: string; // string for select value; "" means no category
  tags: string; // comma-separated
}

type UploadPhase =
  | "idle"
  | "uploading"
  | "done"
  | "error";

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

// ─── Component ────────────────────────────────────────────────────────────────

export default function UploadPage() {
  const router = useRouter();
  const { user, loading, getIdToken } = useAuth();

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

  // Redirect unauthenticated users to login.
  useEffect(() => {
    if (!loading && !user) {
      router.replace("/login");
    }
  }, [user, loading, router]);

  // ─── Handlers ──────────────────────────────────────────────────────────────

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
    // Use a local flag instead of reading the `phase` state value, which is
    // captured by closure and will not reflect updates made by the .catch()
    // handler before the guard below runs.
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
      const msg =
        err instanceof Error ? err.message : "Upload failed.";
      setErrorMessage(msg);
      setPhase("error");
    });

    if (!uploadFailed) {
      setPhase("done");
      // Redirect to the dashboard showing the video as "Processing".
      // Use a generic dashboard route rather than a user-profile URL to avoid
      // depending on the Firebase displayName (client-controlled, may be null).
      router.replace(`/dashboard?uploaded=${videoId}`);
    }
  }

  // ─── Render ────────────────────────────────────────────────────────────────

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <p className="text-gray-500">Loading…</p>
      </div>
    );
  }

  if (!user) {
    return null;
  }

  return (
    <div className="min-h-screen bg-gray-50 flex items-start justify-center py-12 px-4">
      <div className="w-full max-w-xl bg-white rounded-2xl shadow-md p-8 space-y-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Upload video</h1>
          <p className="mt-1 text-sm text-gray-500">
            Supported formats: MP4, MOV, AVI, WebM
          </p>
        </div>

        {errorMessage && (
          <div
            role="alert"
            className="rounded-lg bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-700"
          >
            {errorMessage}
          </div>
        )}

        {fileSizeWarning && (
          <div
            role="note"
            className="rounded-lg bg-yellow-50 border border-yellow-200 px-4 py-3 text-sm text-yellow-800"
          >
            Warning: file is larger than {formatBytes(UPLOAD_SIZE_WARNING_BYTES)}.
            Uploads may take a long time on slow connections.
          </div>
        )}

        {mimeTypeError && (
          <div
            role="alert"
            className="rounded-lg bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-700"
          >
            Unsupported file type. Please select an MP4, MOV, AVI, or WebM
            video file.
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-5">
          {/* File picker */}
          <div>
            <label
              htmlFor="video-file"
              className="block text-sm font-medium text-gray-700 mb-1"
            >
              Video file <span className="text-red-500">*</span>
            </label>
            <input
              id="video-file"
              type="file"
              accept={ACCEPTED_VIDEO_MIME_TYPES.map((t) => t).join(",")}
              onChange={handleFileChange}
              disabled={phase === "uploading"}
              className="block w-full text-sm text-gray-500 file:mr-4 file:py-2 file:px-4 file:rounded-lg file:border-0 file:text-sm file:font-semibold file:bg-blue-50 file:text-blue-700 hover:file:bg-blue-100 disabled:opacity-50"
            />
            {file && (
              <p className="mt-1 text-xs text-gray-400">
                {file.name} ({(file.size / (1024 * 1024)).toFixed(1)} MB)
              </p>
            )}
          </div>

          {/* Title */}
          <div>
            <label
              htmlFor="title"
              className="block text-sm font-medium text-gray-700 mb-1"
            >
              Title <span className="text-red-500">*</span>
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
              className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:opacity-50"
            />
          </div>

          {/* Description */}
          <div>
            <label
              htmlFor="description"
              className="block text-sm font-medium text-gray-700 mb-1"
            >
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
              className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:opacity-50 resize-none"
            />
          </div>

          {/* Category */}
          <div>
            <label
              htmlFor="categoryId"
              className="block text-sm font-medium text-gray-700 mb-1"
            >
              Category
            </label>
            <select
              id="categoryId"
              name="categoryId"
              value={form.categoryId}
              onChange={handleFormChange}
              disabled={phase === "uploading"}
              className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:opacity-50 bg-white"
            >
              {/* Category IDs match seeds in api/migrations/0002_seed_categories.up.sql.
                  If that migration changes, these values must be updated to match. */}
              <option value="">— Select a category —</option>
              <option value="1">Education</option>
              <option value="2">Entertainment</option>
              <option value="3">Gaming</option>
              <option value="4">Music</option>
              <option value="5">Other</option>
            </select>
          </div>

          {/* Tags */}
          <div>
            <label
              htmlFor="tags"
              className="block text-sm font-medium text-gray-700 mb-1"
            >
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
              className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:opacity-50"
            />
            <p className="mt-1 text-xs text-gray-400">
              Separate tags with commas
            </p>
          </div>

          {/* Progress bar — visible only when uploading or done */}
          {(phase === "uploading" || phase === "done") && (
            <div aria-label="upload progress">
              <div className="flex justify-between text-xs text-gray-500 mb-1">
                <span>{phase === "done" ? "Upload complete" : "Uploading…"}</span>
                <span>{uploadProgress}%</span>
              </div>
              <div className="w-full bg-gray-200 rounded-full h-2">
                <div
                  role="progressbar"
                  aria-valuenow={uploadProgress}
                  aria-valuemin={0}
                  aria-valuemax={100}
                  className="bg-blue-600 h-2 rounded-full transition-all duration-200"
                  style={{ width: `${uploadProgress}%` }}
                />
              </div>
            </div>
          )}

          {/* Submit */}
          <button
            type="submit"
            disabled={phase === "uploading" || phase === "done"}
            className="w-full rounded-lg bg-blue-600 px-4 py-2 text-sm font-semibold text-white hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            {phase === "uploading" ? "Uploading…" : "Upload video"}
          </button>
        </form>
      </div>
    </div>
  );
}
