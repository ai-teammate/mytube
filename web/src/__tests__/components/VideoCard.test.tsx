/**
 * Unit tests for src/components/VideoCard.tsx
 */
import React from "react";
import { render, screen } from "@testing-library/react";
import type { VideoCardItem } from "@/domain/search";

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

import VideoCard from "@/components/VideoCard";

function makeVideo(overrides: Partial<VideoCardItem> = {}): VideoCardItem {
  return {
    id: "vid-1",
    title: "Test Video",
    thumbnailUrl: "https://cdn.example.com/thumb.jpg",
    viewCount: 1234,
    uploaderUsername: "alice",
    createdAt: "2024-01-15T10:00:00Z",
    ...overrides,
  };
}

describe("VideoCard", () => {
  it("renders the video title", () => {
    render(<VideoCard video={makeVideo()} />);
    expect(screen.getByText("Test Video")).toBeInTheDocument();
  });

  it("renders links to the video watch page", () => {
    render(<VideoCard video={makeVideo()} />);
    // Both the thumbnail link and title link point to the watch page.
    const links = screen.getAllByRole("link", { name: "Test Video" });
    expect(links.length).toBeGreaterThanOrEqual(1);
    links.forEach((link) => {
      expect(link).toHaveAttribute("href", "/v/vid-1");
    });
  });

  it("renders the thumbnail when provided", () => {
    render(<VideoCard video={makeVideo()} />);
    const img = screen.getByAltText("Test Video");
    expect(img).toHaveAttribute("src", "https://cdn.example.com/thumb.jpg");
  });

  it("renders 'No thumbnail' placeholder when thumbnailUrl is null", () => {
    render(<VideoCard video={makeVideo({ thumbnailUrl: null })} />);
    expect(screen.getByText("No thumbnail")).toBeInTheDocument();
  });

  it("renders the uploader username", () => {
    render(<VideoCard video={makeVideo()} />);
    expect(screen.getByText("alice")).toBeInTheDocument();
  });

  it("renders a link to the uploader profile", () => {
    render(<VideoCard video={makeVideo()} />);
    const link = screen.getByRole("link", { name: "alice" });
    expect(link).toHaveAttribute("href", "/u/alice");
  });

  it("renders formatted view count", () => {
    render(<VideoCard video={makeVideo({ viewCount: 1234567 })} />);
    // toLocaleString produces 1,234,567 on en-US
    expect(screen.getByText(/1,234,567 views/)).toBeInTheDocument();
  });

  it("renders the created date", () => {
    render(<VideoCard video={makeVideo({ createdAt: "2024-01-15T00:00:00Z" })} />);
    // Date is localized; just assert it appears in the document
    // The text includes the view count and date separated by "·"
    expect(screen.getByText(/\d+\/\d+\/\d+/)).toBeInTheDocument();
  });

  it("renders zero views correctly", () => {
    render(<VideoCard video={makeVideo({ viewCount: 0 })} />);
    expect(screen.getByText(/0 views/)).toBeInTheDocument();
  });

  it("has accessible aria-label on thumbnail link", () => {
    render(<VideoCard video={makeVideo({ title: "Accessible Video" })} />);
    // Multiple links may match; just ensure at least one exists.
    const links = screen.getAllByRole("link", { name: "Accessible Video" });
    expect(links.length).toBeGreaterThanOrEqual(1);
  });
});
