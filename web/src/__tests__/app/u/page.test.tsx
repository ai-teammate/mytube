/**
 * Unit tests for src/app/u/[username]/page.tsx
 */
import React from "react";
import { render, screen, waitFor } from "@testing-library/react";
import type { UserProfile } from "@/domain/userProfile";

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
    // eslint-disable-next-line @next/next/no-img-element
    // Strip next/image-specific props that are not valid HTML attributes.
    // eslint-disable-next-line @typescript-eslint/no-unused-vars
    const { fill: _fill, ...rest } = props;
    // eslint-disable-next-line @next/next/no-img-element
    return <img src={src} alt={alt} {...rest} />;
  },
}));

// ─── Mock the data repository ─────────────────────────────────────────────────
// The mock factory captures a stable stub object so there are no hoisting TDZ
// issues.  Individual tests control behaviour via mockImplementation.
const getByUsernameMock = jest.fn<Promise<UserProfile | null>, [string]>();

jest.mock("@/data/userProfileRepository", () => {
  // Factory uses a local reference to avoid the outer-scope TDZ.
  const fn = jest.fn<Promise<UserProfile | null>, [string]>();
  return {
    ApiUserProfileRepository: jest.fn().mockImplementation(() => ({
      getByUsername: fn,
    })),
    // Export the inner mock so tests can control it via __mocks__.
    __getByUsernameFn: fn,
  };
});

// After jest.mock is hoisted and the factory executed, retrieve the stable fn.
// eslint-disable-next-line @typescript-eslint/no-require-imports
const { __getByUsernameFn: fn } = require("@/data/userProfileRepository") as {
  __getByUsernameFn: typeof getByUsernameMock;
};

// ─── Import page AFTER mocks ──────────────────────────────────────────────────
import UserProfilePage from "@/app/u/[username]/page";

// ─── Tests ────────────────────────────────────────────────────────────────────

describe("UserProfilePage", () => {
  beforeEach(() => {
    fn.mockReset();
  });

  it("shows loading state initially", () => {
    fn.mockReturnValue(new Promise(() => {}));

    render(<UserProfilePage params={{ username: "alice" }} />);

    expect(screen.getByText(/loading/i)).toBeInTheDocument();
  });

  it("shows not-found message when profile is null", async () => {
    fn.mockResolvedValue(null);

    render(<UserProfilePage params={{ username: "unknown" }} />);

    await waitFor(() => {
      expect(screen.getByText(/user not found/i)).toBeInTheDocument();
    });
  });

  it("shows error message when repository throws", async () => {
    fn.mockRejectedValue(new Error("network failure"));

    render(<UserProfilePage params={{ username: "alice" }} />);

    await waitFor(() => {
      expect(screen.getByRole("alert")).toHaveTextContent(
        /could not load profile/i
      );
    });
  });

  it("renders username heading when profile is loaded", async () => {
    fn.mockResolvedValue({
      username: "alice",
      avatarUrl: "https://example.com/avatar.png",
      videos: [],
    });

    render(<UserProfilePage params={{ username: "alice" }} />);

    await waitFor(() => {
      expect(
        screen.getByRole("heading", { name: "alice" })
      ).toBeInTheDocument();
    });
  });

  it("renders avatar image when avatarUrl is set", async () => {
    fn.mockResolvedValue({
      username: "alice",
      avatarUrl: "https://example.com/avatar.png",
      videos: [],
    });

    render(<UserProfilePage params={{ username: "alice" }} />);

    await waitFor(() => {
      const avatar = screen.getByAltText("alice's avatar");
      expect(avatar).toHaveAttribute("src", "https://example.com/avatar.png");
    });
  });

  it("renders initials fallback when avatarUrl is null", async () => {
    fn.mockResolvedValue({
      username: "bob",
      avatarUrl: null,
      videos: [],
    });

    render(<UserProfilePage params={{ username: "bob" }} />);

    await waitFor(() => {
      expect(screen.getByLabelText("bob's avatar")).toHaveTextContent("B");
    });
  });

  it("renders 'No videos yet.' when video list is empty", async () => {
    fn.mockResolvedValue({
      username: "carol",
      avatarUrl: null,
      videos: [],
    });

    render(<UserProfilePage params={{ username: "carol" }} />);

    await waitFor(() => {
      expect(screen.getByText(/no videos yet/i)).toBeInTheDocument();
    });
  });

  it("renders video cards for each video", async () => {
    fn.mockResolvedValue({
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
    });

    render(<UserProfilePage params={{ username: "dave" }} />);

    await waitFor(() => {
      expect(screen.getByText("First Video")).toBeInTheDocument();
    });
    expect(screen.getByText("Second Video")).toBeInTheDocument();
    expect(screen.getByText("No thumbnail")).toBeInTheDocument();
  });

  it("each video card links to /v/:id", async () => {
    fn.mockResolvedValue({
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
    });

    render(<UserProfilePage params={{ username: "eve" }} />);

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

    fn.mockResolvedValue({
      username: "frank",
      avatarUrl: null,
      videos,
    });

    render(<UserProfilePage params={{ username: "frank" }} />);

    await waitFor(() => {
      expect(
        screen.getByText(/showing the 50 most recent videos/i)
      ).toBeInTheDocument();
    });
  });

  it("does not show cap notice when fewer than 50 videos are returned", async () => {
    fn.mockResolvedValue({
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
    });

    render(<UserProfilePage params={{ username: "grace" }} />);

    await waitFor(() => {
      expect(screen.getByText("Single Video")).toBeInTheDocument();
    });
    expect(
      screen.queryByText(/showing the 50 most recent videos/i)
    ).not.toBeInTheDocument();
  });

  it("calls getByUsername with the correct username param", async () => {
    fn.mockResolvedValue({
      username: "testuser",
      avatarUrl: null,
      videos: [],
    });

    render(<UserProfilePage params={{ username: "testuser" }} />);

    await waitFor(() => {
      expect(fn).toHaveBeenCalledWith("testuser");
    });
  });

  it("renders thumbnail image when thumbnailUrl is provided", async () => {
    fn.mockResolvedValue({
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
    });

    render(<UserProfilePage params={{ username: "hank" }} />);

    await waitFor(() => {
      expect(screen.getByText("With Thumb")).toBeInTheDocument();
    });
    const thumbImg = screen.getByAltText("With Thumb");
    expect(thumbImg).toHaveAttribute("src", "https://example.com/t.jpg");
  });
});
