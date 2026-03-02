/**
 * Unit tests for src/app/u/[username]/page.tsx
 */
import React from "react";
import { render, screen, waitFor } from "@testing-library/react";
import type { UserProfile, UserProfileRepository } from "@/domain/userProfile";

// ─── Mock React.use to unwrap Promise synchronously in tests ──────────────────
// In production, React.use() suspends the component until the Promise resolves.
// In tests, we resolve the Promise synchronously so rendering is immediate.
jest.mock("react", () => {
  const actual = jest.requireActual<typeof React>("react");
  return {
    ...actual,
    use: jest.fn(<T,>(p: Promise<T> | T): T => {
      // If it's a thenable (Promise), extract the resolved value synchronously
      // via the internal _value trick used by Promise.resolve().
      // Fall back to casting for non-Promise values.
      if (p && typeof (p as Promise<T>).then === "function") {
        // Jest runs in Node.js; resolved promises expose their value here.
        // We rely on Promise.resolve() wrapping the value so (p as any)._value
        // may not exist — instead we use a simpler approach: the test creates
        // Promise.resolve(value), and we store the value on the mock below.
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

// ─── Import page AFTER mocks ──────────────────────────────────────────────────
import UserProfilePage from "@/app/u/[username]/UserProfilePageClient";

// ─── Helper: create a params Promise that React.use can unwrap in tests ───────
function makeParams(username: string): Promise<{ username: string }> {
  const p = Promise.resolve({ username });
  // Attach the resolved value so the React.use mock can extract it synchronously.
  (p as unknown as { __value: { username: string } }).__value = { username };
  return p;
}

// ─── Helper: create a stub repository ────────────────────────────────────────
function makeRepo(
  impl: (username: string) => Promise<UserProfile | null>
): UserProfileRepository {
  return { getByUsername: impl };
}

// ─── Tests ────────────────────────────────────────────────────────────────────

describe("UserProfilePage", () => {
  it("shows loading state initially", () => {
    const repo = makeRepo(() => new Promise(() => {}));

    render(
      <UserProfilePage params={makeParams("alice")} repository={repo} />
    );

    expect(screen.getByText(/loading/i)).toBeInTheDocument();
  });

  it("shows not-found message when profile is null", async () => {
    const repo = makeRepo(() => Promise.resolve(null));

    render(
      <UserProfilePage params={makeParams("unknown")} repository={repo} />
    );

    await waitFor(() => {
      expect(screen.getByText(/user not found/i)).toBeInTheDocument();
    });
  });

  it("shows error message when repository throws", async () => {
    const repo = makeRepo(() => Promise.reject(new Error("network failure")));

    render(
      <UserProfilePage params={makeParams("alice")} repository={repo} />
    );

    await waitFor(() => {
      expect(screen.getByRole("alert")).toHaveTextContent(
        /could not load profile/i
      );
    });
  });

  it("renders username heading when profile is loaded", async () => {
    const repo = makeRepo(() =>
      Promise.resolve({
        username: "alice",
        avatarUrl: "https://example.com/avatar.png",
        videos: [],
      })
    );

    render(
      <UserProfilePage params={makeParams("alice")} repository={repo} />
    );

    await waitFor(() => {
      expect(
        screen.getByRole("heading", { name: "alice" })
      ).toBeInTheDocument();
    });
  });

  it("renders avatar image when avatarUrl is set", async () => {
    const repo = makeRepo(() =>
      Promise.resolve({
        username: "alice",
        avatarUrl: "https://example.com/avatar.png",
        videos: [],
      })
    );

    render(
      <UserProfilePage params={makeParams("alice")} repository={repo} />
    );

    await waitFor(() => {
      const avatar = screen.getByAltText("alice's avatar");
      expect(avatar).toHaveAttribute("src", "https://example.com/avatar.png");
    });
  });

  it("renders initials fallback when avatarUrl is null", async () => {
    const repo = makeRepo(() =>
      Promise.resolve({ username: "bob", avatarUrl: null, videos: [] })
    );

    render(
      <UserProfilePage params={makeParams("bob")} repository={repo} />
    );

    await waitFor(() => {
      expect(screen.getByLabelText("bob's avatar")).toHaveTextContent("B");
    });
  });

  it("renders 'No videos yet.' when video list is empty", async () => {
    const repo = makeRepo(() =>
      Promise.resolve({ username: "carol", avatarUrl: null, videos: [] })
    );

    render(
      <UserProfilePage params={makeParams("carol")} repository={repo} />
    );

    await waitFor(() => {
      expect(screen.getByText(/no videos yet/i)).toBeInTheDocument();
    });
  });

  it("renders video cards for each video", async () => {
    const repo = makeRepo(() =>
      Promise.resolve({
        username: "dave",
        avatarUrl: null,
        videos: [
          {
            id: "v1",
            title: "First Video",
            thumbnailUrl: "https://example.com/thumb.jpg",
            viewCount: 100,
            createdAt: "2024-01-15T10:00:00Z",
          },
          {
            id: "v2",
            title: "Second Video",
            thumbnailUrl: null,
            viewCount: 5,
            createdAt: "2024-01-10T10:00:00Z",
          },
        ],
      })
    );

    render(
      <UserProfilePage params={makeParams("dave")} repository={repo} />
    );

    await waitFor(() => {
      expect(screen.getByText("First Video")).toBeInTheDocument();
    });
    expect(screen.getByText("Second Video")).toBeInTheDocument();
    expect(screen.getByText("No thumbnail")).toBeInTheDocument();
  });

  it("each video card links to /v/:id", async () => {
    const repo = makeRepo(() =>
      Promise.resolve({
        username: "eve",
        avatarUrl: null,
        videos: [
          {
            id: "video-abc-123",
            title: "Test Video",
            thumbnailUrl: null,
            viewCount: 0,
            createdAt: "2024-01-01T00:00:00Z",
          },
        ],
      })
    );

    render(
      <UserProfilePage params={makeParams("eve")} repository={repo} />
    );

    await waitFor(() => {
      expect(screen.getByText("Test Video")).toBeInTheDocument();
    });

    const link = screen.getByRole("link");
    expect(link).toHaveAttribute("href", "/v/video-abc-123");
  });

  it("shows cap notice when exactly 50 videos are returned", async () => {
    const videos = Array.from({ length: 50 }, (_, i) => ({
      id: `v${i}`,
      title: `Video ${i}`,
      thumbnailUrl: null,
      viewCount: 0,
      createdAt: "2024-01-01T00:00:00Z",
    }));

    const repo = makeRepo(() =>
      Promise.resolve({ username: "frank", avatarUrl: null, videos })
    );

    render(
      <UserProfilePage params={makeParams("frank")} repository={repo} />
    );

    await waitFor(() => {
      expect(
        screen.getByText(/showing the 50 most recent videos/i)
      ).toBeInTheDocument();
    });
  });

  it("does not show cap notice when fewer than 50 videos are returned", async () => {
    const repo = makeRepo(() =>
      Promise.resolve({
        username: "grace",
        avatarUrl: null,
        videos: [
          {
            id: "v1",
            title: "Single Video",
            thumbnailUrl: null,
            viewCount: 3,
            createdAt: "2024-01-01T00:00:00Z",
          },
        ],
      })
    );

    render(
      <UserProfilePage params={makeParams("grace")} repository={repo} />
    );

    await waitFor(() => {
      expect(screen.getByText("Single Video")).toBeInTheDocument();
    });
    expect(
      screen.queryByText(/showing the 50 most recent videos/i)
    ).not.toBeInTheDocument();
  });

  it("calls getByUsername with the correct username param", async () => {
    const getByUsername = jest.fn<Promise<UserProfile | null>, [string]>(
      () =>
        Promise.resolve({ username: "testuser", avatarUrl: null, videos: [] })
    );
    const repo: UserProfileRepository = { getByUsername };

    render(
      <UserProfilePage params={makeParams("testuser")} repository={repo} />
    );

    await waitFor(() => {
      expect(getByUsername).toHaveBeenCalledWith("testuser");
    });
  });

  it("renders thumbnail image when thumbnailUrl is provided", async () => {
    const repo = makeRepo(() =>
      Promise.resolve({
        username: "hank",
        avatarUrl: null,
        videos: [
          {
            id: "v99",
            title: "With Thumb",
            thumbnailUrl: "https://example.com/t.jpg",
            viewCount: 1,
            createdAt: "2024-01-01T00:00:00Z",
          },
        ],
      })
    );

    render(
      <UserProfilePage params={makeParams("hank")} repository={repo} />
    );

    await waitFor(() => {
      expect(screen.getByText("With Thumb")).toBeInTheDocument();
    });
    const thumbImg = screen.getByAltText("With Thumb");
    expect(thumbImg).toHaveAttribute("src", "https://example.com/t.jpg");
  });
});
