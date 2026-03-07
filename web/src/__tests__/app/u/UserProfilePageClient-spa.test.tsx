/**
 * Reproduction test for MYTUBE-286: User profile page /u/[username] renders
 * "User not found" on GitHub Pages instead of the actual profile.
 *
 * Root cause: UserProfilePageClient.tsx reads the username directly from the
 * URL param (which is "_" after the SPA redirect) and never checks
 * sessionStorage.__spa_username. Fix mirrors WatchPageClient.tsx.
 */

import React from "react";
import { render, screen, waitFor } from "@testing-library/react";
import type { UserProfile, UserProfileRepository } from "@/domain/userProfile";
import type { PlaylistRepository } from "@/domain/playlist";

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

import UserProfilePage from "@/app/u/[username]/UserProfilePageClient";

// ─── Helpers ──────────────────────────────────────────────────────────────────

function makeParams(username: string): Promise<{ username: string }> {
  const p = Promise.resolve({ username });
  (p as unknown as { __value: { username: string } }).__value = { username };
  return p;
}

function makePlaylistRepo(): PlaylistRepository {
  return {
    getByID: jest.fn(),
    create: jest.fn(),
    listMine: jest.fn().mockResolvedValue([]),
    listByUsername: jest.fn().mockResolvedValue([]),
    updateTitle: jest.fn(),
    deletePlaylist: jest.fn(),
    addVideo: jest.fn(),
    removeVideo: jest.fn(),
  };
}

function makeProfile(username: string): UserProfile {
  return {
    username,
    displayName: username,
    avatarUrl: null,
    videos: [
      {
        id: "video-abc-123",
        title: "Test Video",
        thumbnailUrl: null,
        viewCount: 5,
        createdAt: "2024-01-01T00:00:00Z",
      },
    ],
  };
}

// ─── Tests ────────────────────────────────────────────────────────────────────

describe("UserProfilePageClient — GitHub Pages SPA fallback (MYTUBE-286)", () => {
  afterEach(() => {
    sessionStorage.clear();
    jest.restoreAllMocks();
  });

  it("loads profile using username stored in sessionStorage when params.username is '_'", async () => {
    // This is the bug reproduction: 404.html sets __spa_username and redirects
    // to /u/_/. UserProfilePageClient must read the real username from
    // sessionStorage instead of passing '_' to the repository.
    const realUsername = "tester";
    const getByUsername = jest.fn<
      Promise<UserProfile | null>,
      [string]
    >(() => Promise.resolve(makeProfile(realUsername)));
    const repo: UserProfileRepository = { getByUsername };

    sessionStorage.setItem("__spa_username", realUsername);

    render(
      <UserProfilePage
        params={makeParams("_")}
        repository={repo}
        playlistRepository={makePlaylistRepo()}
      />
    );

    // The component must resolve the real username and call getByUsername with it.
    await waitFor(() => {
      expect(getByUsername).toHaveBeenCalledWith(realUsername);
    });

    // '_' must never reach the API.
    expect(getByUsername).not.toHaveBeenCalledWith("_");

    // sessionStorage key must be cleared to avoid stale redirects on refresh.
    expect(sessionStorage.getItem("__spa_username")).toBeNull();
  });

  it("renders the username heading after loading via the SPA fallback", async () => {
    const realUsername = "tester";
    const repo: UserProfileRepository = {
      getByUsername: jest.fn(() =>
        Promise.resolve(makeProfile(realUsername))
      ),
    };

    sessionStorage.setItem("__spa_username", realUsername);

    render(
      <UserProfilePage
        params={makeParams("_")}
        repository={repo}
        playlistRepository={makePlaylistRepo()}
      />
    );

    await waitFor(() => {
      expect(
        screen.getByRole("heading", { name: realUsername })
      ).toBeInTheDocument();
    });
  });

  it("falls back to params.username when sessionStorage has no entry (direct /u/_/ access)", async () => {
    // If someone navigates directly to /u/_/ (the placeholder shell), the
    // component should try to load '_' as-is and show "User not found".
    const getByUsername = jest.fn<Promise<UserProfile | null>, [string]>(() =>
      Promise.resolve(null)
    );
    const repo: UserProfileRepository = { getByUsername };

    // sessionStorage is empty — no redirect occurred
    render(
      <UserProfilePage
        params={makeParams("_")}
        repository={repo}
        playlistRepository={makePlaylistRepo()}
      />
    );

    await waitFor(() => {
      expect(getByUsername).toHaveBeenCalledWith("_");
    });
  });

  it("uses params.username directly when it is not the placeholder '_'", async () => {
    // Normal client-side navigation passes a real username in params;
    // the sessionStorage fallback must not interfere.
    const realUsername = "alice";
    const getByUsername = jest.fn<Promise<UserProfile | null>, [string]>(() =>
      Promise.resolve(makeProfile(realUsername))
    );
    const repo: UserProfileRepository = { getByUsername };

    // Even if there's a stale entry in sessionStorage, it should be ignored
    // because params.username is already a real username.
    sessionStorage.setItem("__spa_username", "stale-user");

    render(
      <UserProfilePage
        params={makeParams(realUsername)}
        repository={repo}
        playlistRepository={makePlaylistRepo()}
      />
    );

    await waitFor(() => {
      expect(getByUsername).toHaveBeenCalledWith(realUsername);
    });
    expect(getByUsername).not.toHaveBeenCalledWith("stale-user");
  });

  it("corrects the browser URL after SPA redirect (does not call replaceState with '_')", async () => {
    const realUsername = "tester";
    const repo: UserProfileRepository = {
      getByUsername: jest.fn(() =>
        Promise.resolve(makeProfile(realUsername))
      ),
    };

    const replaceState = jest.spyOn(window.history, "replaceState");

    sessionStorage.setItem("__spa_username", realUsername);

    render(
      <UserProfilePage
        params={makeParams("_")}
        repository={repo}
        playlistRepository={makePlaylistRepo()}
      />
    );

    // Wait for the profile to load — by this time the URL correction effect
    // has also run.
    await waitFor(() => {
      expect(
        screen.getByRole("heading", { name: realUsername })
      ).toBeInTheDocument();
    });

    // replaceState must not have been called with a path containing '_'
    // (the placeholder shell username).
    const calledWithUnderscore = replaceState.mock.calls.some(
      ([, , url]) => typeof url === "string" && url.includes("/u/_/")
    );
    expect(calledWithUnderscore).toBe(false);
  });
});
