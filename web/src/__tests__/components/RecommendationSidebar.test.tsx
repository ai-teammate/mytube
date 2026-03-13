/**
 * Unit tests for RecommendationSidebar component.
 */
import React from "react";
import { render, screen, waitFor } from "@testing-library/react";
import type { RecommendationRepository } from "@/domain/video";
import type { VideoCardItem } from "@/domain/search";

// ─── Mocks ────────────────────────────────────────────────────────────────────

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

jest.mock("next/navigation", () => ({
  useRouter: () => ({ push: jest.fn() }),
}));

import RecommendationSidebar from "@/components/RecommendationSidebar";

// ─── Helpers ──────────────────────────────────────────────────────────────────

function makeVideoCardItem(overrides: Partial<VideoCardItem> = {}): VideoCardItem {
  return {
    id: "vid-2",
    title: "Related Video",
    thumbnailUrl: "https://cdn.example.com/thumb.jpg",
    viewCount: 100,
    uploaderUsername: "bob",
    createdAt: "2024-01-15T10:00:00Z",
    ...overrides,
  };
}

function makeRepo(videos: VideoCardItem[]): RecommendationRepository {
  return {
    getRecommendations: jest.fn().mockResolvedValue(videos),
  };
}

function makeFailingRepo(): RecommendationRepository {
  return {
    getRecommendations: jest.fn().mockRejectedValue(new Error("network error")),
  };
}

// ─── Tests ────────────────────────────────────────────────────────────────────

describe("RecommendationSidebar", () => {
  it("shows skeleton loader while fetching", () => {
    const repo: RecommendationRepository = {
      getRecommendations: jest.fn(() => new Promise(() => {})),
    };

    render(<RecommendationSidebar videoID="vid-1" repository={repo} />);

    expect(
      screen.getByLabelText("Loading recommendations")
    ).toBeInTheDocument();
  });

  it("renders 'More like this' heading when >=2 recommendations are returned", async () => {
    const videos = [
      makeVideoCardItem({ id: "r1" }),
      makeVideoCardItem({ id: "r2" }),
    ];
    render(<RecommendationSidebar videoID="vid-1" repository={makeRepo(videos)} />);

    await waitFor(() => {
      expect(screen.getByRole("heading", { name: "More like this" })).toBeInTheDocument();
    });
  });

  it("renders all returned video cards", async () => {
    const videos = [
      makeVideoCardItem({ id: "r1", title: "First Related" }),
      makeVideoCardItem({ id: "r2", title: "Second Related" }),
      makeVideoCardItem({ id: "r3", title: "Third Related" }),
    ];
    render(<RecommendationSidebar videoID="vid-1" repository={makeRepo(videos)} />);

    await waitFor(() => {
      expect(screen.getByText("First Related")).toBeInTheDocument();
      expect(screen.getByText("Second Related")).toBeInTheDocument();
      expect(screen.getByText("Third Related")).toBeInTheDocument();
    });
  });

  it("renders nothing (returns null) when fewer than 2 recommendations are returned", async () => {
    render(
      <RecommendationSidebar
        videoID="vid-1"
        repository={makeRepo([makeVideoCardItem({ id: "r1" })])}
      />
    );

    await waitFor(() => {
      expect(screen.queryByRole("heading", { name: "More like this" })).not.toBeInTheDocument();
    });
  });

  it("renders nothing when recommendations array is empty", async () => {
    const { container } = render(
      <RecommendationSidebar videoID="vid-1" repository={makeRepo([])} />
    );

    await waitFor(() => {
      expect(screen.queryByRole("heading", { name: "More like this" })).not.toBeInTheDocument();
    });
    expect(container.firstChild).toBeNull();
  });

  it("renders nothing silently when repository throws an error", async () => {
    const { container } = render(
      <RecommendationSidebar videoID="vid-1" repository={makeFailingRepo()} />
    );

    await waitFor(() => {
      expect(screen.queryByText("More like this")).not.toBeInTheDocument();
    });
    expect(container.firstChild).toBeNull();
  });

  it("calls getRecommendations with the correct videoID", async () => {
    const getRecommendations = jest.fn().mockResolvedValue([]);
    const repo: RecommendationRepository = { getRecommendations };

    render(<RecommendationSidebar videoID="video-abc" repository={repo} />);

    await waitFor(() => {
      expect(getRecommendations).toHaveBeenCalledWith("video-abc");
    });
  });

  it("re-fetches when videoID changes", async () => {
    const getRecommendations = jest.fn().mockResolvedValue([]);
    const repo: RecommendationRepository = { getRecommendations };

    const { rerender } = render(
      <RecommendationSidebar videoID="vid-1" repository={repo} />
    );

    await waitFor(() => {
      expect(getRecommendations).toHaveBeenCalledWith("vid-1");
    });

    rerender(<RecommendationSidebar videoID="vid-2" repository={repo} />);

    await waitFor(() => {
      expect(getRecommendations).toHaveBeenCalledWith("vid-2");
    });
  });

  it("renders exactly 8 video cards when 8 are returned", async () => {
    const videos = Array.from({ length: 8 }, (_, i) =>
      makeVideoCardItem({ id: `r${i + 1}`, title: `Video ${i + 1}` })
    );
    render(<RecommendationSidebar videoID="vid-1" repository={makeRepo(videos)} />);

    await waitFor(() => {
      expect(screen.getByText("More like this")).toBeInTheDocument();
    });

    // All 8 video titles should be rendered.
    for (let i = 1; i <= 8; i++) {
      expect(screen.getByText(`Video ${i}`)).toBeInTheDocument();
    }
  });
});
