/**
 * Unit tests for src/app/page.tsx (HomePage)
 */
import React from "react";
import { render, screen, waitFor } from "@testing-library/react";
import type { VideoCardItem, DiscoveryRepository } from "@/domain/search";

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

// ─── Mock next/navigation for SiteHeader ──────────────────────────────────────
jest.mock("next/navigation", () => ({
  useRouter: () => ({ push: jest.fn() }),
}));

// ─── Import page AFTER mocks ──────────────────────────────────────────────────
import HomePage from "@/app/page";

// ─── Helpers ──────────────────────────────────────────────────────────────────

function makeVideo(id: string, title: string): VideoCardItem {
  return {
    id,
    title,
    thumbnailUrl: null,
    viewCount: 10,
    uploaderUsername: "alice",
    createdAt: "2024-01-15T10:00:00Z",
  };
}

function makeRepo(
  getRecent: () => Promise<VideoCardItem[]>,
  getPopular: () => Promise<VideoCardItem[]>
): DiscoveryRepository {
  return { getRecent, getPopular };
}

// ─── Tests ────────────────────────────────────────────────────────────────────

describe("HomePage", () => {
  it("shows loading state initially", () => {
    const repo = makeRepo(
      () => new Promise(() => {}),
      () => new Promise(() => {})
    );

    render(<HomePage repository={repo} />);
    expect(screen.getByText(/loading/i)).toBeInTheDocument();
  });

  it("renders 'Recently Uploaded' section heading after load", async () => {
    const repo = makeRepo(
      () => Promise.resolve([makeVideo("v1", "Recent Video")]),
      () => Promise.resolve([])
    );

    render(<HomePage repository={repo} />);

    await waitFor(() => {
      expect(screen.getByRole("heading", { name: /recently uploaded/i })).toBeInTheDocument();
    });
  });

  it("renders 'Most Viewed' section heading after load", async () => {
    const repo = makeRepo(
      () => Promise.resolve([]),
      () => Promise.resolve([makeVideo("p1", "Popular Video")])
    );

    render(<HomePage repository={repo} />);

    await waitFor(() => {
      expect(screen.getByRole("heading", { name: /most viewed/i })).toBeInTheDocument();
    });
  });

  it("renders video cards in recently uploaded section", async () => {
    const repo = makeRepo(
      () => Promise.resolve([
        makeVideo("v1", "Recent Video 1"),
        makeVideo("v2", "Recent Video 2"),
      ]),
      () => Promise.resolve([])
    );

    render(<HomePage repository={repo} />);

    await waitFor(() => {
      expect(screen.getByText("Recent Video 1")).toBeInTheDocument();
      expect(screen.getByText("Recent Video 2")).toBeInTheDocument();
    });
  });

  it("renders video cards in most viewed section", async () => {
    const repo = makeRepo(
      () => Promise.resolve([]),
      () => Promise.resolve([makeVideo("p1", "Popular Video 1")])
    );

    render(<HomePage repository={repo} />);

    await waitFor(() => {
      expect(screen.getByText("Popular Video 1")).toBeInTheDocument();
    });
  });

  it("shows 'No videos yet' when recent videos is empty", async () => {
    const repo = makeRepo(
      () => Promise.resolve([]),
      () => Promise.resolve([])
    );

    render(<HomePage repository={repo} />);

    await waitFor(() => {
      // There will be two "No videos yet." for both sections
      const messages = screen.getAllByText("No videos yet.");
      expect(messages.length).toBeGreaterThanOrEqual(1);
    });
  });

  it("shows error message when repository throws", async () => {
    const repo = makeRepo(
      () => Promise.reject(new Error("network failure")),
      () => Promise.reject(new Error("network failure"))
    );

    render(<HomePage repository={repo} />);

    await waitFor(() => {
      expect(screen.getByRole("alert")).toHaveTextContent(
        /could not load videos/i
      );
    });
  });

  it("does not show loading state after data loads", async () => {
    const repo = makeRepo(
      () => Promise.resolve([]),
      () => Promise.resolve([])
    );

    render(<HomePage repository={repo} />);

    await waitFor(() => {
      expect(screen.queryByText(/loading/i)).not.toBeInTheDocument();
    });
  });

  it("calls getRecent and getPopular on mount", async () => {
    const getRecent = jest.fn(() => Promise.resolve([]));
    const getPopular = jest.fn(() => Promise.resolve([]));
    const repo: DiscoveryRepository = { getRecent, getPopular };

    render(<HomePage repository={repo} />);

    await waitFor(() => {
      expect(getRecent).toHaveBeenCalledWith(20);
      expect(getPopular).toHaveBeenCalledWith(20);
    });
  });
});
