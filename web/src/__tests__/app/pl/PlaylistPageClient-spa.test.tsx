/**
 * Reproduction test for MYTUBE-592: Playlist detail page shows
 * "Could not load playlist" error.
 *
 * Root cause: PlaylistPageClient.tsx did not implement the GitHub Pages SPA
 * sessionStorage fallback. public/404.html stores the real playlist UUID in
 * sessionStorage.__spa_playlist_id and redirects to the pre-built shell at
 * /pl/_/. The component received params.id = "_", sent GET /api/playlists/_,
 * which failed isValidUUID("_") validation → 400 → catch block → error message.
 *
 * Fix: apply the same lazy-state / sessionStorage / history.replaceState
 * pattern used by WatchPageClient and UserProfilePageClient.
 */

import React from "react";
import { render, screen, waitFor } from "@testing-library/react";
import type { PlaylistDetail, PlaylistRepository } from "@/domain/playlist";
import type { VideoRepository } from "@/domain/video";

// ─── Mocks ────────────────────────────────────────────────────────────────────

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

jest.mock("next/dynamic", () => ({
  __esModule: true,
  default: () => {
    function MockVideoPlayer({ src }: { src: string }) {
      return <div data-testid="video-player" data-src={src} />;
    }
    return MockVideoPlayer;
  },
}));

jest.mock("@/data/videoRepository", () => ({
  ApiVideoRepository: jest.fn().mockImplementation(() => ({
    getByID: jest.fn().mockResolvedValue(null),
  })),
}));

import PlaylistPageClient from "@/app/pl/[id]/PlaylistPageClient";

// ─── Helpers ──────────────────────────────────────────────────────────────────

function makeParams(id: string): Promise<{ id: string }> {
  const p = Promise.resolve({ id });
  (p as unknown as { __value: { id: string } }).__value = { id };
  return p;
}

function makePlaylistDetail(
  overrides: Partial<PlaylistDetail> = {}
): PlaylistDetail {
  return {
    id: "00000000-0000-0000-0000-000000000099",
    title: "SPA Test Playlist",
    ownerUsername: "alice",
    videos: [],
    ...overrides,
  };
}

function makeRepo(
  overrides: Partial<PlaylistRepository> = {}
): PlaylistRepository {
  return {
    getByID: jest.fn().mockResolvedValue(makePlaylistDetail()),
    create: jest.fn(),
    listMine: jest.fn(),
    listByUsername: jest.fn(),
    updateTitle: jest.fn(),
    deletePlaylist: jest.fn(),
    addVideo: jest.fn(),
    removeVideo: jest.fn(),
    ...overrides,
  };
}

function makeVideoRepo(
  overrides: Partial<VideoRepository> = {}
): VideoRepository {
  return {
    getByID: jest.fn().mockResolvedValue(null),
    ...overrides,
  };
}

// ─── Tests ────────────────────────────────────────────────────────────────────

describe("PlaylistPageClient — GitHub Pages SPA fallback (MYTUBE-592)", () => {
  afterEach(() => {
    sessionStorage.clear();
    jest.clearAllMocks();
  });

  it("loads playlist using the UUID stored in sessionStorage when params.id is '_'", async () => {
    // This is the bug reproduction: 404.html sets __spa_playlist_id and redirects
    // to /pl/_/ (the pre-built shell). PlaylistPageClient must read the real UUID
    // from sessionStorage instead of passing '_' to the repository.
    const realId = "00000000-0000-0000-0000-000000000099";
    const getByID = jest.fn<Promise<PlaylistDetail | null>, [string]>(() =>
      Promise.resolve(makePlaylistDetail({ id: realId }))
    );
    const repo = makeRepo({ getByID });

    sessionStorage.setItem("__spa_playlist_id", realId);

    render(
      <PlaylistPageClient
        params={makeParams("_")}
        repository={repo}
        videoRepository={makeVideoRepo()}
      />
    );

    // The component should resolve the real UUID and call getByID with it.
    await waitFor(() => {
      expect(getByID).toHaveBeenCalledWith(realId);
    });

    // '_' must never reach the API.
    expect(getByID).not.toHaveBeenCalledWith("_");

    // sessionStorage key must be cleared to avoid stale redirects on refresh.
    expect(sessionStorage.getItem("__spa_playlist_id")).toBeNull();
  });

  it("renders the playlist title after loading via the SPA fallback", async () => {
    const realId = "00000000-0000-0000-0000-000000000099";
    const repo = makeRepo({
      getByID: jest.fn(() =>
        Promise.resolve(makePlaylistDetail({ title: "SPA Test Playlist" }))
      ),
    });

    sessionStorage.setItem("__spa_playlist_id", realId);

    render(
      <PlaylistPageClient
        params={makeParams("_")}
        repository={repo}
        videoRepository={makeVideoRepo()}
      />
    );

    await waitFor(() => {
      expect(
        screen.getByRole("heading", { name: "SPA Test Playlist" })
      ).toBeInTheDocument();
    });
  });

  it("falls back to params.id when sessionStorage has no entry (direct /pl/_/ access)", async () => {
    // If someone navigates directly to /pl/_/ (the placeholder shell), the
    // component should try to load '_' as-is.
    const getByID = jest.fn<Promise<PlaylistDetail | null>, [string]>(() =>
      Promise.resolve(null)
    );
    const repo = makeRepo({ getByID });

    // sessionStorage is empty — no 404 redirect occurred
    render(
      <PlaylistPageClient
        params={makeParams("_")}
        repository={repo}
        videoRepository={makeVideoRepo()}
      />
    );

    await waitFor(() => {
      expect(getByID).toHaveBeenCalledWith("_");
    });
  });

  it("uses params.id directly when it is not the placeholder '_'", async () => {
    // Normal client-side navigation passes a real UUID as params;
    // sessionStorage fallback must not interfere.
    const realId = "00000000-0000-0000-0000-000000000099";
    const getByID = jest.fn<Promise<PlaylistDetail | null>, [string]>(() =>
      Promise.resolve(makePlaylistDetail({ id: realId }))
    );
    const repo = makeRepo({ getByID });

    // Even with a stale entry in sessionStorage, the real params.id is used.
    sessionStorage.setItem("__spa_playlist_id", "stale-id");

    render(
      <PlaylistPageClient
        params={makeParams(realId)}
        repository={repo}
        videoRepository={makeVideoRepo()}
      />
    );

    await waitFor(() => {
      expect(getByID).toHaveBeenCalledWith(realId);
    });
    expect(getByID).not.toHaveBeenCalledWith("stale-id");
  });
});

// ─── MYTUBE-604: HTTP 400 (invalid UUID) UX ───────────────────────────────────

describe("PlaylistPageClient — HTTP 400 invalid UUID (MYTUBE-604)", () => {
  afterEach(() => {
    sessionStorage.clear();
    jest.clearAllMocks();
  });

  it("shows 'Playlist not found.' when repository returns null for a 400 (invalid UUID)", async () => {
    // The repository returns null for both 404 and 400 responses.
    // PlaylistPageClient must render the notFound state ('Playlist not found.')
    // rather than the generic error message.
    const getByID = jest.fn<Promise<PlaylistDetail | null>, [string]>(() =>
      Promise.resolve(null)
    );
    const repo = makeRepo({ getByID });

    render(
      <PlaylistPageClient
        params={makeParams("not-a-valid-uuid-123")}
        repository={repo}
        videoRepository={makeVideoRepo()}
      />
    );

    await waitFor(() => {
      expect(screen.getByText("Playlist not found.")).toBeInTheDocument();
    });

    // Must NOT show the generic connection-failure error.
    expect(
      screen.queryByText("Could not load playlist. Please try again later.")
    ).not.toBeInTheDocument();
  });
});
