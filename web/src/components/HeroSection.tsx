"use client";

import React from "react";
import Link from "next/link";
import Image from "next/image";
import styles from "./HeroSection.module.css";

// ─── Constants ────────────────────────────────────────────────────────────────

const HERO_PILLS = ["Upload & Share", "HLS Streaming", "Playlists & Discovery"] as const;

const QUALITY_BADGES: { label: string; active: boolean }[] = [
  { label: "1080p", active: true },
  { label: "720p", active: false },
  { label: "480p", active: false },
];

interface StatCard {
  icon: IconType;
  label: string;
  description: string;
}

const STAT_CARDS: StatCard[] = [
  { icon: "lock", label: "100% Private", description: "Your videos, your rules" },
  { icon: "play", label: "HLS Quality", description: "Adaptive bitrate playback" },
  { icon: "star", label: "Free Forever", description: "No subscriptions ever" },
];

// ─── Types ────────────────────────────────────────────────────────────────────

type IconType = "lock" | "play" | "star";

export interface HeroSectionProps {
  /** Optional thumbnail URL for the visual panel canvas (e.g. first video thumbnail). */
  thumbnailUrl?: string | null;
}

// ─── Component ────────────────────────────────────────────────────────────────

export default function HeroSection({ thumbnailUrl }: HeroSectionProps) {
  function handleBrowseLibrary() {
    document.getElementById("video-grid")?.scrollIntoView({ behavior: "smooth" });
  }

  return (
    <section aria-label="Hero" className={styles.hero}>
      {/* ── Left column ── */}
      <div className={styles.heroContent}>
        {/* Feature pills row */}
        <div className={styles.pillRow}>
          {HERO_PILLS.map((label) => (
            <span key={label} className={styles.pill}>
              {label}
            </span>
          ))}
        </div>

        {/* Headline */}
        <h1 className={styles.headline}>MYTUBE: personal video portal</h1>

        {/* Sub-text */}
        <p className={styles.subText}>
          Your personal space to upload, stream, and discover videos — powered by HLS adaptive
          streaming and Google Cloud.
        </p>

        {/* CTA buttons */}
        <div className={styles.heroActions}>
          <Link href="/upload" className="btn cta">
            Upload Your First Video
          </Link>
          <button
            type="button"
            onClick={handleBrowseLibrary}
            className="btn ghost"
            aria-label="Browse Library"
          >
            Browse Library
          </button>
        </div>

        {/* Stat cards */}
        <div className={styles.statCards}>
          {STAT_CARDS.map((card) => (
            <div key={card.label} className={styles.heroCard}>
              <StatIcon type={card.icon} />
              <span className={styles.cardLabel}>{card.label}</span>
              <span className={styles.cardDesc}>{card.description}</span>
            </div>
          ))}
        </div>
      </div>

      {/* ── Right column: visual panel ── */}
      <div className={styles.visualPanel} aria-hidden="true">
        <div className={styles.frostedOverlay}>
          <p className={styles.visualTitle}>Personal Playback Preview</p>

          {/* Quality badge pills */}
          <div className={styles.qualityBadges}>
            {QUALITY_BADGES.map((badge) => (
              <span
                key={badge.label}
                className={badge.active ? styles.badgeActive : styles.badge}
              >
                {badge.label}
              </span>
            ))}
          </div>

          {/* Thumbnail / canvas area */}
          <div className={styles.visualCanvas}>
            {thumbnailUrl ? (
              <Image
                src={thumbnailUrl}
                alt="Video preview"
                fill
                style={{ objectFit: "cover" }}
                unoptimized
              />
            ) : (
              <div className={styles.canvasPlaceholder} data-testid="canvas-placeholder" />
            )}
          </div>
        </div>
      </div>
    </section>
  );
}

// ─── Inline SVG icon components ───────────────────────────────────────────────

function StatIcon({ type }: { type: IconType }) {
  const shared = {
    "aria-hidden": true as const,
    width: 24,
    height: 24,
    viewBox: "0 0 24 24",
    fill: "none",
    stroke: "currentColor",
    strokeWidth: 1.5,
    strokeLinecap: "round" as const,
    strokeLinejoin: "round" as const,
  };

  if (type === "lock") {
    return (
      <svg {...shared}>
        <rect x="3" y="11" width="18" height="11" rx="2" ry="2" />
        <path d="M7 11V7a5 5 0 0 1 10 0v4" />
      </svg>
    );
  }

  if (type === "play") {
    return (
      <svg {...shared}>
        <circle cx="12" cy="12" r="10" />
        <polygon points="10 8 16 12 10 16 10 8" fill="currentColor" stroke="none" />
      </svg>
    );
  }

  // star
  return (
    <svg {...shared}>
      <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2" />
    </svg>
  );
}
