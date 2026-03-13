/**
 * Reproduction test for MYTUBE-280: Video watch page /v/[id] renders home page
 * instead of Video.js player on GitHub Pages.
 *
 * Root cause: deploy-pages.yml copies out/index.html → out/404.html, so GitHub
 * Pages serves the pre-rendered *homepage* HTML for any unknown /v/<uuid>/ URL.
 * The Next.js App Router hydrates that DOM as the homepage and cannot route to the
 * watch page because no RSC payload exists for the non-pre-generated UUID.
 *
 * Fix: public/404.html stores the real UUID in sessionStorage and redirects to the
 * pre-built watch-page shell at /v/_/. WatchPageClient reads the UUID from
 * sessionStorage (lazy useState initialiser) when params.id === '_', then
 * updates the browser URL via history.replaceState.
 */

import React from "react";
import { render, screen, waitFor } from "@testing-library/react";
import type { VideoDetail, VideoRepository } from "@/domain/video";
import type { RecommendationRepository } from "@/domain/video";
import type { RatingRepository } from "@/domain/rating";
import type { CommentRepository } from "@/domain/comment";
import type { PlaylistRepository } from "@/domain/playlist";

// ─── Mocks (mirrors page.test.tsx setup) ─────────────────────────────────────

jest.mock("@/context/AuthContext", () => ({
  useAuth: () => ({
    user: { email: "test@example.com" },
    loading: false,
    getIdToken: jest.fn().mockResolvedValue(null),
  }),
}));

jest.mock("react", () => {
  const actual = jest.requireActual<typeof React>("react");
  return {
    ...actual,
    use: jest.fn(<T,>(p: Promise<T> | T): T => {
      if (p && typeof (p as Promise<T>).then === "function") {
        return (p as unknown as { __value: T }).__value;
      }
      return p as T;
    }),
  };
});

jest.mock("next/image", () => ({
  __esModule: true,
  default: function MockImage({
    src,
    alt,
    ...props
  }: {
    src: string;
    alt: string;
    [key: string]: unknown;
  }) {
    // eslint-disable-next-line @typescript-eslint/no-unused-vars
    const { fill: _fill, ...rest } = props;
    // eslint-disable-next-line @next/next/no-img-element
    return <img src={src} alt={alt} {...rest} />;
  },
}));

jest.mock("next/dynamic", () => ({
  __esModule: true,
  default: () => {
    function MockVideoPlayer({ src }: { src: string }) {
      return <div data-testid="video-player" data-src={src} />;
    }
    return MockVideoPlayer;
  },
}));

import WatchPage from "@/app/v/[id]/WatchPageClient";

// ─── Helpers ──────────────────────────────────────────────────────────────────

function makeParams(id: string): Promise<{ id: string }> {
  const p = Promise.resolve({ id });
  (p as unknown as { __value: { id: string } }).__value = { id };
  return p;
}

function makeRatingRepo(): RatingRepository {
  return {
    getSummary: jest.fn().mockResolvedValue({
      averageRating: 0,
      ratingCount: 0,
      myRating: null,
    }),
    submitRating: jest.fn().mockResolvedValue({
      averageRating: 0,
      ratingCount: 0,
      myRating: null,
    }),
  };
}

function makeCommentRepo(): CommentRepository {
  return {
    listByVideoID: jest.fn().mockResolvedValue([]),
    create: jest.fn().mockResolvedValue({}),
    deleteComment: jest.fn().mockResolvedValue(undefined),
  };
}

function makePlaylistRepo(): PlaylistRepository {
  return {
    getByID: jest.fn(),
    create: jest.fn(),
    listMine: jest.fn().mockResolvedValue([]),
    listByUsername: jest.fn(),
    updateTitle: jest.fn(),
    deletePlaylist: jest.fn(),
    addVideo: jest.fn(),
    removeVideo: jest.fn(),
  };
}

function makeRecommendationRepo(): RecommendationRepository {
  return {
    getRecommendations: jest.fn().mockResolvedValue([]),
  };
}

function makeVideo(overrides: Partial<VideoDetail> = {}): VideoDetail {
  return {
    id: "e8adb1b2-14d3-4baf-a734-7f03532213b5",
    title: "SPA Test Video",
    description: "A video loaded via the SPA fallback",
    hlsManifestUrl:
      "https://cdn.example.com/videos/e8adb1b2/index.m3u8",
    thumbnailUrl: "https://cdn.example.com/thumb.jpg",
    viewCount: 42,
    createdAt: "2024-01-15T10:00:00Z",
    status: "ready",
    uploader: { username: "alice", avatarUrl: null },
    tags: [],
    ...overrides,
  };
}

// ─── Tests ────────────────────────────────────────────────────────────────────

describe("WatchPageClient — GitHub Pages SPA fallback (MYTUBE-280)", () => {
  afterEach(() => {
    sessionStorage.clear();
  });

  it("loads video using the UUID stored in sessionStorage when params.id is '_'", async () => {
    // This is the bug reproduction: 404.html sets __spa_video_id and redirects
    // to /v/_/ (the pre-built shell). WatchPageClient must read the real UUID
    // from sessionStorage instead of passing '_' to the repository.
    const realId = "e8adb1b2-14d3-4baf-a734-7f03532213b5";
    const getByID = jest.fn<Promise<VideoDetail | null>, [string]>(() =>
      Promise.resolve(makeVideo({ id: realId }))
    );
    const repo: VideoRepository = { getByID };

    sessionStorage.setItem("__spa_video_id", realId);

    render(
      <WatchPage
        params={makeParams("_")}
        repository={repo}
        recommendationRepository={makeRecommendationRepo()}
        ratingRepository={makeRatingRepo()}
        commentRepository={makeCommentRepo()}
        playlistRepository={makePlaylistRepo()}
      />
    );

    // The component should resolve the real UUID and call getByID with it.
    await waitFor(() => {
      expect(getByID).toHaveBeenCalledWith(realId);
    });

    // '_' must never reach the API.
    expect(getByID).not.toHaveBeenCalledWith("_");

    // sessionStorage key must be cleared to avoid stale redirects on refresh.
    expect(sessionStorage.getItem("__spa_video_id")).toBeNull();
  });

  it("renders the video title after loading via the SPA fallback", async () => {
    const realId = "e8adb1b2-14d3-4baf-a734-7f03532213b5";
    const repo: VideoRepository = {
      getByID: jest.fn(() =>
        Promise.resolve(makeVideo({ title: "SPA Test Video" }))
      ),
    };

    sessionStorage.setItem("__spa_video_id", realId);

    render(
      <WatchPage
        params={makeParams("_")}
        repository={repo}
        recommendationRepository={makeRecommendationRepo()}
        ratingRepository={makeRatingRepo()}
        commentRepository={makeCommentRepo()}
        playlistRepository={makePlaylistRepo()}
      />
    );

    await waitFor(() => {
      expect(
        screen.getByRole("heading", { name: "SPA Test Video" })
      ).toBeInTheDocument();
    });
  });

  it("falls back to params.id when sessionStorage has no entry (direct /v/_/ access)", async () => {
    // If someone navigates directly to /v/_/ (the placeholder shell), the
    // component should try to load '_' as-is and show "Video not found".
    const getByID = jest.fn<Promise<VideoDetail | null>, [string]>(() =>
      Promise.resolve(null)
    );
    const repo: VideoRepository = { getByID };

    // sessionStorage is empty — no redirect occurred
    render(
      <WatchPage
        params={makeParams("_")}
        repository={repo}
        recommendationRepository={makeRecommendationRepo()}
        ratingRepository={makeRatingRepo()}
        commentRepository={makeCommentRepo()}
        playlistRepository={makePlaylistRepo()}
      />
    );

    await waitFor(() => {
      expect(getByID).toHaveBeenCalledWith("_");
    });
  });

  it("uses params.id directly when it is not the placeholder '_'", async () => {
    // Normal client-side navigation (e.g. VideoCard <Link>) passes a real UUID
    // as params; sessionStorage fallback must not interfere.
    const realId = "e8adb1b2-14d3-4baf-a734-7f03532213b5";
    const getByID = jest.fn<Promise<VideoDetail | null>, [string]>(() =>
      Promise.resolve(makeVideo({ id: realId }))
    );
    const repo: VideoRepository = { getByID };

    // Even if there's a stale entry in sessionStorage, it should be ignored
    // because params.id is already a real video UUID.
    sessionStorage.setItem("__spa_video_id", "stale-id");

    render(
      <WatchPage
        params={makeParams(realId)}
        repository={repo}
        recommendationRepository={makeRecommendationRepo()}
        ratingRepository={makeRatingRepo()}
        commentRepository={makeCommentRepo()}
        playlistRepository={makePlaylistRepo()}
      />
    );

    await waitFor(() => {
      expect(getByID).toHaveBeenCalledWith(realId);
    });
    expect(getByID).not.toHaveBeenCalledWith("stale-id");
  });
});
