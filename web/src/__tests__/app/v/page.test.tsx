/**
 * Unit tests for src/app/v/[id]/page.tsx
 */
import React from "react";
import { render, screen, waitFor } from "@testing-library/react";
import type { VideoDetail, VideoRepository } from "@/domain/video";
import type { RecommendationRepository } from "@/domain/video";
import type { RatingRepository } from "@/domain/rating";
import type { CommentRepository } from "@/domain/comment";
import type { PlaylistRepository } from "@/domain/playlist";

// ─── Mock useAuth ─────────────────────────────────────────────────────────────
jest.mock("@/context/AuthContext", () => ({
  useAuth: () => ({
    user: { email: "test@example.com" },
    loading: false,
    getIdToken: jest.fn().mockResolvedValue(null),
  }),
}));

// ─── Mock next/navigation (required by VideoCard inside RecommendationSidebar) ─
jest.mock("next/navigation", () => ({
  useRouter: () => ({ push: jest.fn() }),
}));

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

// ─── Mock next/image ──────────────────────────────────────────────────────────
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

// ─── Mock next/dynamic (VideoPlayer) ─────────────────────────────────────────
// Replace the dynamic VideoPlayer import with a simple stub.
jest.mock("next/dynamic", () => ({
  __esModule: true,
  default: () => {
    function MockVideoPlayer({ src }: { src: string }) {
      return <div data-testid="video-player" data-src={src} />;
    }
    return MockVideoPlayer;
  },
}));

// ─── Import page AFTER mocks ──────────────────────────────────────────────────
import WatchPage from "@/app/v/[id]/WatchPageClient";

// ─── Helpers ──────────────────────────────────────────────────────────────────

function makeParams(id: string): Promise<{ id: string }> {
  const p = Promise.resolve({ id });
  (p as unknown as { __value: { id: string } }).__value = { id };
  return p;
}

function makeRepo(
  impl: (id: string) => Promise<VideoDetail | null>
): VideoRepository {
  return { getByID: impl };
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

function makeRecommendationRepo(
  videos: object[] = []
): RecommendationRepository {
  return {
    getRecommendations: jest.fn().mockResolvedValue(videos),
  };
}

// Render WatchPage with default stub repos to avoid real fetch calls.
function renderWatchPage(repo: VideoRepository, videoID = "vid-1") {
  return render(
    <WatchPage
      params={makeParams(videoID)}
      repository={repo}
      recommendationRepository={makeRecommendationRepo()}
      ratingRepository={makeRatingRepo()}
      commentRepository={makeCommentRepo()}
      playlistRepository={makePlaylistRepo()}
    />
  );
}

function makeVideo(overrides: Partial<VideoDetail> = {}): VideoDetail {
  return {
    id: "vid-1",
    title: "Test Video",
    description: "A great video",
    hlsManifestUrl: "https://cdn.example.com/videos/vid-1/index.m3u8",
    thumbnailUrl: "https://cdn.example.com/thumb.jpg",
    viewCount: 42,
    createdAt: "2024-01-15T10:00:00Z",
    status: "ready",
    uploader: {
      username: "alice",
      avatarUrl: "https://example.com/avatar.png",
    },
    tags: ["go", "programming"],
    ...overrides,
  };
}

// ─── Tests ────────────────────────────────────────────────────────────────────

describe("WatchPage", () => {
  it("shows skeleton loading state initially", () => {
    const repo = makeRepo(() => new Promise(() => {}));

    renderWatchPage(repo, "vid-1");

    // WatchPageSkeleton renders skeleton elements with aria-hidden while loading.
    expect(screen.getAllByRole("main")[0]).toBeInTheDocument();
    // Verify no real content (title, description) is shown yet
    expect(screen.queryByRole("heading", { level: 1 })).not.toBeInTheDocument();
  });

  it("shows not-found message when video is null", async () => {
    const repo = makeRepo(() => Promise.resolve(null));

    renderWatchPage(repo, "nonexistent");

    await waitFor(() => {
      expect(screen.getByText(/video not found/i)).toBeInTheDocument();
    });
  });

  it("shows error message when repository throws", async () => {
    const repo = makeRepo(() => Promise.reject(new Error("network failure")));

    renderWatchPage(repo, "vid-1");

    await waitFor(() => {
      expect(screen.getByRole("alert")).toHaveTextContent(
        /could not load video/i
      );
    });
  });

  it("renders video title as heading when loaded", async () => {
    const repo = makeRepo(() => Promise.resolve(makeVideo()));

    renderWatchPage(repo, "vid-1");

    await waitFor(() => {
      expect(
        screen.getByRole("heading", { name: "Test Video" })
      ).toBeInTheDocument();
    });
  });

  it("renders VideoPlayer with hls_manifest_url as src", async () => {
    const repo = makeRepo(() => Promise.resolve(makeVideo()));

    renderWatchPage(repo, "vid-1");

    await waitFor(() => {
      const player = screen.getByTestId("video-player");
      expect(player).toHaveAttribute(
        "data-src",
        "https://cdn.example.com/videos/vid-1/index.m3u8"
      );
    });
  });

  it("shows 'Video not available yet.' when hlsManifestUrl is null", async () => {
    const repo = makeRepo(() =>
      Promise.resolve(makeVideo({ hlsManifestUrl: null }))
    );

    renderWatchPage(repo, "vid-1");

    await waitFor(() => {
      expect(
        screen.getByText(/video not available yet/i)
      ).toBeInTheDocument();
    });
  });

  it("renders uploader username as a link to /u/:username", async () => {
    const repo = makeRepo(() => Promise.resolve(makeVideo()));

    renderWatchPage(repo, "vid-1");

    await waitFor(() => {
      const link = screen.getByRole("link", { name: "alice" });
      expect(link).toHaveAttribute("href", "/u/alice");
    });
  });

  it("renders uploader avatar when avatarUrl is set", async () => {
    const repo = makeRepo(() => Promise.resolve(makeVideo()));

    renderWatchPage(repo, "vid-1");

    await waitFor(() => {
      const avatar = screen.getByAltText("alice's avatar");
      expect(avatar).toHaveAttribute("src", "https://example.com/avatar.png");
    });
  });

  it("renders uploader initials fallback when avatarUrl is null", async () => {
    const repo = makeRepo(() =>
      Promise.resolve(
        makeVideo({
          uploader: { username: "bob", avatarUrl: null },
        })
      )
    );

    renderWatchPage(repo, "vid-1");

    await waitFor(() => {
      expect(screen.getByLabelText("bob's avatar")).toHaveTextContent("B");
    });
  });

  it("renders tags as chips", async () => {
    const repo = makeRepo(() =>
      Promise.resolve(makeVideo({ tags: ["golang", "tutorial"] }))
    );

    renderWatchPage(repo, "vid-1");

    await waitFor(() => {
      expect(screen.getByText("golang")).toBeInTheDocument();
      expect(screen.getByText("tutorial")).toBeInTheDocument();
    });
  });

  it("renders no tags section when tags is empty", async () => {
    const repo = makeRepo(() => Promise.resolve(makeVideo({ tags: [] })));

    renderWatchPage(repo, "vid-1");

    await waitFor(() => {
      // Title should render but no tag chips
      expect(screen.getByRole("heading", { name: "Test Video" })).toBeInTheDocument();
    });
    // Tags like 'go' and 'programming' should not exist
    expect(screen.queryByText("go")).not.toBeInTheDocument();
  });

  it("renders description when present", async () => {
    const repo = makeRepo(() =>
      Promise.resolve(makeVideo({ description: "This is my description" }))
    );

    renderWatchPage(repo, "vid-1");

    await waitFor(() => {
      expect(
        screen.getByText("This is my description")
      ).toBeInTheDocument();
    });
  });

  it("renders no description section when description is null", async () => {
    const repo = makeRepo(() =>
      Promise.resolve(makeVideo({ description: null }))
    );

    renderWatchPage(repo, "vid-1");

    await waitFor(() => {
      expect(screen.getByRole("heading", { name: "Test Video" })).toBeInTheDocument();
    });
    expect(screen.queryByText(/a great video/i)).not.toBeInTheDocument();
  });

  it("displays formatted view count", async () => {
    const repo = makeRepo(() =>
      Promise.resolve(makeVideo({ viewCount: 1234567 }))
    );

    renderWatchPage(repo, "vid-1");

    await waitFor(() => {
      // toLocaleString formats large numbers with commas
      expect(screen.getByText(/1,234,567 views/i)).toBeInTheDocument();
    });
  });

  it("calls getByID with the correct video id param", async () => {
    const getByID = jest.fn<Promise<VideoDetail | null>, [string]>(() =>
      Promise.resolve(makeVideo())
    );
    const repo: VideoRepository = { getByID };

    renderWatchPage(repo, "my-video-id");

    await waitFor(() => {
      expect(getByID).toHaveBeenCalledWith("my-video-id");
    });
  });

  it("renders Save to Playlist button when video is loaded", async () => {
    const repo = makeRepo(() => Promise.resolve(makeVideo()));

    renderWatchPage(repo, "vid-1");

    await waitFor(() => {
      expect(
        screen.getByRole("button", { name: /save to playlist/i })
      ).toBeInTheDocument();
    });
  });

  it("renders sidebar recommendations section when >=2 recommendations are returned", async () => {
    const recommendations = [
      { id: "r1", title: "Related 1", thumbnailUrl: null, viewCount: 10, uploaderUsername: "bob", createdAt: "2024-01-01T00:00:00Z" },
      { id: "r2", title: "Related 2", thumbnailUrl: null, viewCount: 5, uploaderUsername: "carol", createdAt: "2024-01-02T00:00:00Z" },
    ];
    render(
      <WatchPage
        params={makeParams("vid-1")}
        repository={makeRepo(() => Promise.resolve(makeVideo()))}
        recommendationRepository={makeRecommendationRepo(recommendations)}
        ratingRepository={makeRatingRepo()}
        commentRepository={makeCommentRepo()}
        playlistRepository={makePlaylistRepo()}
      />
    );

    await waitFor(() => {
      expect(screen.getByText("More like this")).toBeInTheDocument();
    });
  });

  it("hides sidebar recommendations section when <2 recommendations are returned", async () => {
    render(
      <WatchPage
        params={makeParams("vid-1")}
        repository={makeRepo(() => Promise.resolve(makeVideo()))}
        recommendationRepository={makeRecommendationRepo([])}
        ratingRepository={makeRatingRepo()}
        commentRepository={makeCommentRepo()}
        playlistRepository={makePlaylistRepo()}
      />
    );

    await waitFor(() => {
      expect(screen.getByRole("heading", { name: "Test Video" })).toBeInTheDocument();
    });
    expect(screen.queryByText("More like this")).not.toBeInTheDocument();
  });

  it("renders 'Rate this video' heading from StarRating widget", async () => {
    const repo = makeRepo(() => Promise.resolve(makeVideo()));

    renderWatchPage(repo, "vid-1");

    await waitFor(() => {
      expect(screen.getByText("Rate this video")).toBeInTheDocument();
    });
  });

  it("renders view count in meta line below title", async () => {
    const repo = makeRepo(() =>
      Promise.resolve(makeVideo({ viewCount: 99 }))
    );

    renderWatchPage(repo, "vid-1");

    await waitFor(() => {
      expect(screen.getByText(/99 views/i)).toBeInTheDocument();
    });
  });
});
