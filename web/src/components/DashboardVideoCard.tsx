"use client";

import Image from "next/image";
import Link from "next/link";
import type { DashboardVideo } from "@/domain/dashboard";
import styles from "./DashboardVideoCard.module.css";

// ─── Constants ────────────────────────────────────────────────────────────────

const STATUS_LABELS: Record<DashboardVideo["status"], string> = {
  ready: "Ready",
  processing: "Processing",
  pending: "Pending",
  failed: "Failed",
};

const STATUS_CSS: Record<DashboardVideo["status"], string> = {
  ready: styles.statusReady,
  processing: styles.statusProcessing,
  pending: styles.statusPending,
  failed: styles.statusFailed,
};

// ─── Props ────────────────────────────────────────────────────────────────────

export interface DashboardVideoCardProps {
  video: DashboardVideo;
  onEdit: (video: DashboardVideo) => void;
  onDelete: (videoId: string) => void;
  /** True only when this card's delete is in progress (spinner/disabled). */
  isDeleting: boolean;
  /** True when delete confirmation row is shown for this card. */
  isConfirmingDelete: boolean;
  onConfirmDelete: () => void;
  onCancelDelete: () => void;
}

// ─── Component ────────────────────────────────────────────────────────────────

export default function DashboardVideoCard({
  video,
  onEdit,
  onDelete,
  isDeleting,
  isConfirmingDelete,
  onConfirmDelete,
  onCancelDelete,
}: DashboardVideoCardProps) {
  return (
    <div className={styles.card}>
      {/* Thumbnail with status badge overlay */}
      <div className={styles.thumb}>
        {video.thumbnailUrl ? (
          <Image
            src={video.thumbnailUrl}
            alt={`${video.title} thumbnail`}
            fill
            className="object-cover"
          />
        ) : (
          <div className={styles.thumbPlaceholder}>No thumbnail</div>
        )}
        <span className={`${styles.statusBadge} ${STATUS_CSS[video.status]}`}>
          {STATUS_LABELS[video.status]}
        </span>
      </div>

      {/* Card body */}
      <div className={styles.body}>
        {video.status === "ready" ? (
          <Link href={`/v/${video.id}`} className={styles.title}>
            {video.title}
          </Link>
        ) : (
          <span className={styles.title}>{video.title}</span>
        )}

        <div className={styles.meta}>
          <span>{video.viewCount.toLocaleString()} views</span>
          <span aria-hidden="true">·</span>
          <span>{new Date(video.createdAt).toLocaleDateString()}</span>
        </div>

        {/* Action row: Edit + Delete (with inline confirm) */}
        <div className={styles.actions}>
          <button
            onClick={() => onEdit(video)}
            aria-label={`Edit ${video.title}`}
            className={styles.btnEdit}
          >
            Edit
          </button>

          {isConfirmingDelete ? (
            <span className={styles.deleteConfirm}>
              <button
                onClick={onConfirmDelete}
                disabled={isDeleting}
                className={styles.btnConfirm}
              >
                {isDeleting ? "Deleting…" : "Confirm"}
              </button>
              <button
                onClick={onCancelDelete}
                disabled={isDeleting}
                className={styles.btnCancel}
              >
                Cancel
              </button>
            </span>
          ) : (
            <button
              onClick={() => onDelete(video.id)}
              aria-label={`Delete ${video.title}`}
              className={styles.btnDelete}
            >
              Delete
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
