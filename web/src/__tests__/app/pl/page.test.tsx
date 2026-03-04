/**
 * Unit tests for src/app/pl/[id]/PlaylistPageClient.tsx
 */
import React from "react";
import { render, screen, waitFor, act } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { PlaylistDetail, PlaylistRepository } from "@/domain/playlist";
import type { VideoDetail, VideoRepository } from "@/domain/video";

// ─── Mock React.use to unwrap Promise synchronously in tests ──────────────────
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

// ─── Mock next/dynamic (VideoPlayer) ─────────────────────────────────────────
jest.mock("next/dynamic", () => ({
  __esModule: true,
  default: () => {
    function MockVideoPlayer({ src }: { src: string }) {
      return <div data-testid="video-player" data-src={src} />;
    }
    return MockVideoPlayer;
  },
}));

// ─── Mock data repositories to prevent real network calls ────────────────────
jest.mock("@/data/videoRepository", () => ({
  ApiVideoRepository: jest.fn().mockImplementation(() => ({
    getByID: jest.fn().mockResolvedValue(null),
  })),
}));

// ─── Import page AFTER mocks ──────────────────────────────────────────────────
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
    id: "pl-1",
    title: "My Playlist",
    ownerUsername: "alice",
    videos: [
      {
        id: "v-1",
        title: "Video One",
        thumbnailUrl: "https://cdn.example.com/t1.jpg",
        position: 1,
      },
      { id: "v-2", title: "Video Two", thumbnailUrl: null, position: 2 },
    ],
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

function makeVideoDetail(overrides: Partial<VideoDetail> = {}): VideoDetail {
  return {
    id: "v-1",
    title: "Video One",
    description: null,
    hlsManifestUrl: "https://cdn.example.com/v.m3u8",
    thumbnailUrl: null,
    viewCount: 0,
    createdAt: "2024-01-01T00:00:00Z",
    status: "ready",
    uploader: { username: "alice", avatarUrl: null },
    tags: [],
    ...overrides,
  };
}

function makeVideoRepo(
  overrides: Partial<VideoRepository> = {}
): VideoRepository {
  return {
    getByID: jest.fn().mockResolvedValue(makeVideoDetail()),
    ...overrides,
  };
}

// ─── Tests ────────────────────────────────────────────────────────────────────

describe("PlaylistPageClient", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it("shows loading state initially", () => {
    const repo = makeRepo({
      getByID: jest.fn().mockReturnValue(new Promise(() => {})),
    });
    render(<PlaylistPageClient params={makeParams("pl-1")} repository={repo} />);
    expect(screen.getByText(/loading/i)).toBeInTheDocument();
  });

  it("shows not-found message when playlist is null", async () => {
    const repo = makeRepo({ getByID: jest.fn().mockResolvedValue(null) });
    render(<PlaylistPageClient params={makeParams("pl-1")} repository={repo} />);
    await waitFor(() => {
      expect(screen.getByText(/playlist not found/i)).toBeInTheDocument();
    });
  });

  it("shows error message when repository throws", async () => {
    const repo = makeRepo({
      getByID: jest.fn().mockRejectedValue(new Error("network failure")),
    });
    render(<PlaylistPageClient params={makeParams("pl-1")} repository={repo} />);
    await waitFor(() => {
      expect(screen.getByRole("alert")).toHaveTextContent(
        /could not load playlist/i
      );
    });
  });

  it("renders playlist title as heading", async () => {
    const repo = makeRepo();
    render(<PlaylistPageClient params={makeParams("pl-1")} repository={repo} />);
    await waitFor(() => {
      expect(
        screen.getByRole("heading", { name: "My Playlist" })
      ).toBeInTheDocument();
    });
  });

  it("renders owner username as link to /u/:username", async () => {
    const repo = makeRepo();
    render(<PlaylistPageClient params={makeParams("pl-1")} repository={repo} />);
    await waitFor(() => {
      const link = screen.getByRole("link", { name: "alice" });
      expect(link).toHaveAttribute("href", "/u/alice");
    });
  });

  it("shows video count in subtitle", async () => {
    const repo = makeRepo();
    render(<PlaylistPageClient params={makeParams("pl-1")} repository={repo} />);
    await waitFor(() => {
      expect(screen.getByText(/2 videos/i)).toBeInTheDocument();
    });
  });

  it("shows empty playlist message when playlist has no videos", async () => {
    const repo = makeRepo({
      getByID: jest.fn().mockResolvedValue(
        makePlaylistDetail({ videos: [] })
      ),
    });
    render(<PlaylistPageClient params={makeParams("pl-1")} repository={repo} />);
    await waitFor(() => {
      expect(
        screen.getByText(/this playlist has no videos yet/i)
      ).toBeInTheDocument();
    });
  });

  it("renders queue panel with video buttons", async () => {
    const repo = makeRepo();
    render(<PlaylistPageClient params={makeParams("pl-1")} repository={repo} />);
    await waitFor(() => {
      expect(
        screen.getByRole("button", { name: /play video one/i })
      ).toBeInTheDocument();
      expect(
        screen.getByRole("button", { name: /play video two/i })
      ).toBeInTheDocument();
    });
  });

  it("first video in queue is marked as current", async () => {
    const repo = makeRepo();
    render(<PlaylistPageClient params={makeParams("pl-1")} repository={repo} />);
    await waitFor(() => {
      expect(
        screen.getByRole("button", { name: /play video one/i })
      ).toHaveAttribute("aria-current", "true");
    });
  });

  it("second video in queue is not current initially", async () => {
    const repo = makeRepo();
    render(<PlaylistPageClient params={makeParams("pl-1")} repository={repo} />);
    await waitFor(() => {
      expect(
        screen.getByRole("button", { name: /play video two/i })
      ).not.toHaveAttribute("aria-current");
    });
  });

  it("clicking a queue item marks it as current", async () => {
    const user = userEvent.setup();
    const repo = makeRepo();
    render(<PlaylistPageClient params={makeParams("pl-1")} repository={repo} />);
    await waitFor(() => {
      expect(
        screen.getByRole("button", { name: /play video two/i })
      ).toBeInTheDocument();
    });

    await act(async () => {
      await user.click(screen.getByRole("button", { name: /play video two/i }));
    });

    expect(
      screen.getByRole("button", { name: /play video two/i })
    ).toHaveAttribute("aria-current", "true");
    expect(
      screen.getByRole("button", { name: /play video one/i })
    ).not.toHaveAttribute("aria-current");
  });

  it("shows 'Now playing' info for the current video", async () => {
    const repo = makeRepo();
    render(<PlaylistPageClient params={makeParams("pl-1")} repository={repo} />);
    await waitFor(() => {
      expect(screen.getByText(/now playing/i)).toBeInTheDocument();
    });
  });

  it("shows end-of-playlist overlay when last video ends via Skip", async () => {
    const user = userEvent.setup();
    // videoRepository returns null → PlaylistVideoPlayerWrapper shows Skip button
    const videoRepo = makeVideoRepo({ getByID: jest.fn().mockResolvedValue(null) });
    const repo = makeRepo({
      getByID: jest.fn().mockResolvedValue(
        makePlaylistDetail({
          videos: [
            {
              id: "v-1",
              title: "Only Video",
              thumbnailUrl: null,
              position: 1,
            },
          ],
        })
      ),
    });
    render(
      <PlaylistPageClient
        params={makeParams("pl-1")}
        repository={repo}
        videoRepository={videoRepo}
      />
    );

    await waitFor(() => {
      expect(
        screen.getByRole("button", { name: /skip/i })
      ).toBeInTheDocument();
    });

    await act(async () => {
      await user.click(screen.getByRole("button", { name: /skip/i }));
    });

    expect(screen.getByTestId("end-of-playlist")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /play again/i })
    ).toBeInTheDocument();
  });

  it("Play again button resets to first video", async () => {
    const user = userEvent.setup();
    // videoRepository returns null → PlaylistVideoPlayerWrapper shows Skip button
    const videoRepo = makeVideoRepo({ getByID: jest.fn().mockResolvedValue(null) });
    const repo = makeRepo({
      getByID: jest.fn().mockResolvedValue(
        makePlaylistDetail({
          videos: [
            {
              id: "v-1",
              title: "Only Video",
              thumbnailUrl: null,
              position: 1,
            },
          ],
        })
      ),
    });
    render(
      <PlaylistPageClient
        params={makeParams("pl-1")}
        repository={repo}
        videoRepository={videoRepo}
      />
    );

    await waitFor(() => {
      expect(
        screen.getByRole("button", { name: /skip/i })
      ).toBeInTheDocument();
    });
    await act(async () => {
      await user.click(screen.getByRole("button", { name: /skip/i }));
    });
    expect(screen.getByTestId("end-of-playlist")).toBeInTheDocument();

    await act(async () => {
      await user.click(screen.getByRole("button", { name: /play again/i }));
    });

    expect(screen.queryByTestId("end-of-playlist")).not.toBeInTheDocument();
  });

  it("calls getByID with the correct playlist id", async () => {
    const getByID = jest.fn().mockResolvedValue(makePlaylistDetail());
    const repo = makeRepo({ getByID });
    render(
      <PlaylistPageClient
        params={makeParams("my-playlist-id")}
        repository={repo}
      />
    );
    await waitFor(() => {
      expect(getByID).toHaveBeenCalledWith("my-playlist-id");
    });
  });
});
