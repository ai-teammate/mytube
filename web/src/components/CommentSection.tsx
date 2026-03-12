"use client";

import { useState, useEffect } from "react";
import Image from "next/image";
import Link from "next/link";
import type { Comment, CommentRepository } from "@/domain/comment";
import styles from "./CommentSection.module.css";

interface CommentSectionProps {
  videoID: string;
  repository: CommentRepository;
  /** Returns the current Firebase ID token, or null if not authenticated. */
  getToken: () => Promise<string | null>;
  /** True if the auth state is still being resolved. */
  authLoading?: boolean;
}

/**
 * CommentSection renders the comment list and a submit form below the video.
 *
 * Layout: card-per-comment with gradient avatar circle, username + timestamp
 * meta line, body text. Unauthenticated users see a "Login to comment" prompt.
 * Errors shown as inline text per MYTUBE-161 decision.
 */
export default function CommentSection({
  videoID,
  repository,
  getToken,
  authLoading = false,
}: CommentSectionProps) {
  const [comments, setComments] = useState<Comment[]>([]);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [body, setBody] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [isAuthenticated, setIsAuthenticated] = useState(false);

  // Resolve auth state once on mount (and when authLoading changes).
  // The cancellation guard prevents setState calls on an unmounted component.
  useEffect(() => {
    if (authLoading) return;
    let cancelled = false;
    getToken().then((t) => {
      if (!cancelled) setIsAuthenticated(t !== null);
    });
    return () => {
      cancelled = true;
    };
  }, [authLoading, getToken]);

  // Load comments.
  useEffect(() => {
    let cancelled = false;

    async function load() {
      try {
        const data = await repository.listByVideoID(videoID);
        if (!cancelled) setComments(data);
      } catch {
        if (!cancelled) setLoadError("Could not load comments.");
      }
    }

    load();
    return () => {
      cancelled = true;
    };
  }, [videoID, repository]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSubmitError(null);

    const trimmed = body.trim();
    if (!trimmed) return;

    setSubmitting(true);
    try {
      const token = await getToken();
      if (!token) {
        setSubmitError("Please log in to comment.");
        return;
      }
      const created = await repository.create(videoID, trimmed, token);
      setComments((prev) => [created, ...prev]);
      setBody("");
    } catch {
      setSubmitError("Could not post comment. Please try again.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <section aria-label="Comments" className={styles.section}>
      <h2 className={styles.heading}>Comments</h2>

      {/* Comment form for authenticated users */}
      {!authLoading && isAuthenticated && (
        <form onSubmit={handleSubmit} className={styles.commentForm}>
          <textarea
            aria-label="Comment body"
            value={body}
            onChange={(e) => setBody(e.target.value)}
            placeholder="Add a comment…"
            rows={3}
            disabled={submitting}
            className={styles.commentInput}
          />
          {/* Character counter using Array.from to count Unicode code points
              (matching the server-side utf8.RuneCountInString check) rather
              than UTF-16 code units as would be used by String.length / maxLength. */}
          <p className={styles.charCounter}>
            {Array.from(body).length} / 2000
          </p>
          {submitError && (
            <p role="alert" className={styles.submitError}>
              {submitError}
            </p>
          )}
          <div className={styles.formActions}>
            <button
              type="submit"
              disabled={submitting || body.trim() === "" || Array.from(body).length > 2000}
              className="btn cta"
            >
              {submitting ? "Posting…" : "Comment"}
            </button>
          </div>
        </form>
      )}

      {/* Login prompt for unauthenticated users */}
      {!authLoading && !isAuthenticated && (
        <p className={styles.loginPrompt}>
          <Link href="/login" className={styles.loginLink}>
            Login
          </Link>{" "}
          to comment.
        </p>
      )}

      {/* Error loading comments */}
      {loadError && (
        <p role="alert" className={styles.loadError}>
          {loadError}
        </p>
      )}

      {/* Comment list */}
      {comments.length === 0 && !loadError && (
        <p className={styles.emptyText}>No comments yet.</p>
      )}

      <ul className={styles.commentList}>
        {comments.map((comment) => (
          <li key={comment.id} className={styles.commentItem}>
            <div className={styles.commentInner}>
              {/* Avatar */}
              {comment.author.avatarUrl ? (
                <Image
                  src={comment.author.avatarUrl}
                  alt={`${comment.author.username}'s avatar`}
                  width={36}
                  height={36}
                  className="rounded-full object-cover flex-shrink-0"
                />
              ) : (
                <div
                  className={styles.avatarInitials}
                  aria-label={`${comment.author.username}'s avatar`}
                >
                  {comment.author.username.charAt(0).toUpperCase()}
                </div>
              )}

              {/* Content */}
              <div className={styles.commentContent}>
                <div className={styles.metaLine}>
                  <Link
                    href={`/u/${comment.author.username}`}
                    className={styles.authorLink}
                  >
                    {comment.author.username}
                  </Link>
                  <span className={styles.timestamp}>
                    {new Date(comment.createdAt).toLocaleDateString()}
                  </span>
                </div>
                <p className={styles.commentBody}>
                  {comment.body}
                </p>
              </div>
            </div>
          </li>
        ))}
      </ul>
    </section>
  );
}


interface CommentSectionProps {
  videoID: string;
  repository: CommentRepository;
  /** Returns the current Firebase ID token, or null if not authenticated. */
  getToken: () => Promise<string | null>;
  /** True if the auth state is still being resolved. */
  authLoading?: boolean;
}

/**
 * CommentSection renders the comment list and a submit form below the video.
 *
 * Layout: row-with-avatar (32 px circle, username + timestamp, body below).
 * Unauthenticated users see a "Login to comment" prompt.
 * Errors shown as inline text per MYTUBE-161 decision.
 */
export default function CommentSection({
  videoID,
  repository,
  getToken,
  authLoading = false,
}: CommentSectionProps) {
  const [comments, setComments] = useState<Comment[]>([]);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [body, setBody] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [isAuthenticated, setIsAuthenticated] = useState(false);

  // Resolve auth state once on mount (and when authLoading changes).
  // The cancellation guard prevents setState calls on an unmounted component.
  useEffect(() => {
    if (authLoading) return;
    let cancelled = false;
    getToken().then((t) => {
      if (!cancelled) setIsAuthenticated(t !== null);
    });
    return () => {
      cancelled = true;
    };
  }, [authLoading, getToken]);

  // Load comments.
  useEffect(() => {
    let cancelled = false;

    async function load() {
      try {
        const data = await repository.listByVideoID(videoID);
        if (!cancelled) setComments(data);
      } catch {
        if (!cancelled) setLoadError("Could not load comments.");
      }
    }

    load();
    return () => {
      cancelled = true;
    };
  }, [videoID, repository]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSubmitError(null);

    const trimmed = body.trim();
    if (!trimmed) return;

    setSubmitting(true);
    try {
      const token = await getToken();
      if (!token) {
        setSubmitError("Please log in to comment.");
        return;
      }
      const created = await repository.create(videoID, trimmed, token);
      setComments((prev) => [created, ...prev]);
      setBody("");
    } catch {
      setSubmitError("Could not post comment. Please try again.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <section aria-label="Comments" className="mt-6">
      <h2 className="text-lg font-semibold text-gray-900 mb-4">Comments</h2>

      {/* Comment form for authenticated users */}
      {!authLoading && isAuthenticated && (
        <form onSubmit={handleSubmit} className="flex flex-col gap-2 mb-6">
          <textarea
            aria-label="Comment body"
            value={body}
            onChange={(e) => setBody(e.target.value)}
            placeholder="Add a comment…"
            rows={3}
            disabled={submitting}
            className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:opacity-50 resize-none"
          />
          {/* Character counter using Array.from to count Unicode code points
              (matching the server-side utf8.RuneCountInString check) rather
              than UTF-16 code units as would be used by String.length / maxLength. */}
          <p className="text-xs text-gray-400 text-right">
            {Array.from(body).length} / 2000
          </p>
          {submitError && (
            <p role="alert" className="text-sm text-red-600">
              {submitError}
            </p>
          )}
          <div className="flex justify-end">
            <button
              type="submit"
              disabled={submitting || body.trim() === "" || Array.from(body).length > 2000}
              className="rounded-lg bg-blue-600 px-4 py-1.5 text-sm font-semibold text-white hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              {submitting ? "Posting…" : "Comment"}
            </button>
          </div>
        </form>
      )}

      {/* Login prompt for unauthenticated users */}
      {!authLoading && !isAuthenticated && (
        <p className="text-sm text-gray-600 mb-6">
          <Link href="/login" className="text-blue-600 hover:underline">
            Login
          </Link>{" "}
          to comment.
        </p>
      )}

      {/* Error loading comments */}
      {loadError && (
        <p role="alert" className="text-sm text-red-600 mb-4">
          {loadError}
        </p>
      )}

      {/* Comment list */}
      {comments.length === 0 && !loadError && (
        <p className="text-sm text-gray-500">No comments yet.</p>
      )}

      <ul className="space-y-4">
        {comments.map((comment) => (
          <li key={comment.id} className="flex gap-3">
            {/* Avatar */}
            {comment.author.avatarUrl ? (
              <Image
                src={comment.author.avatarUrl}
                alt={`${comment.author.username}'s avatar`}
                width={32}
                height={32}
                className="rounded-full object-cover flex-shrink-0"
              />
            ) : (
              <div
                className="w-8 h-8 rounded-full bg-gray-300 flex items-center justify-center text-xs font-bold text-gray-600 flex-shrink-0"
                aria-label={`${comment.author.username}'s avatar`}
              >
                {comment.author.username.charAt(0).toUpperCase()}
              </div>
            )}

            {/* Content */}
            <div className="flex-1 min-w-0">
              <div className="flex items-baseline gap-2">
                <Link
                  href={`/u/${comment.author.username}`}
                  className="text-sm font-medium text-gray-900 hover:underline"
                >
                  {comment.author.username}
                </Link>
                <span className="text-xs text-gray-500">
                  {new Date(comment.createdAt).toLocaleDateString()}
                </span>
              </div>
              <p className="mt-0.5 text-sm text-gray-700 whitespace-pre-wrap break-words">
                {comment.body}
              </p>
            </div>
          </li>
        ))}
      </ul>
    </section>
  );
}
