/**
 * MYTUBE-456: VideoCard tags omission — tags row is hidden when video.tags is empty.
 *
 * Objective:
 *   Verify that the VideoCard does not render an empty or broken tags row if no
 *   tags are provided in the data.
 *
 * Preconditions:
 *   A video exists with an empty tags array or null/undefined tags field.
 *
 * Steps:
 *   1. Navigate to the page where this specific video is listed.
 *   2. Observe the area below the video sub-line (category/views).
 *
 * Expected Result:
 *   The .video-tags row is completely omitted from the DOM. There is no empty
 *   space or placeholder where the tags would usually appear.
 */

import React from "react";
import { render } from "@testing-library/react";
import type { VideoCardItem } from "@/domain/search";

// ─── Mock next/navigation ─────────────────────────────────────────────────────

const mockPush = jest.fn();
jest.mock("next/navigation", () => ({
  useRouter: () => ({ push: mockPush }),
}));

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

beforeEach(() => {
  jest.clearAllMocks();
  sessionStorage.clear();
});

function makeVideo(overrides: Partial<VideoCardItem> = {}): VideoCardItem {
  return {
    id: "vid-1",
    title: "Test Video",
    thumbnailUrl: "https://cdn.example.com/thumb.jpg",
    viewCount: 1000,
    uploaderUsername: "testuser",
    createdAt: "2024-01-15T10:00:00Z",
    ...overrides,
  };
}

describe("MYTUBE-456 — VideoCard tags row omission", () => {
  it("does not render the tags container when tags is an empty array", () => {
    const { container } = render(<VideoCard video={makeVideo({ tags: [] })} />);
    // The .videoTags div must be completely absent from the DOM
    const tagsRow = container.querySelector(".videoTags");
    expect(tagsRow).toBeNull();
  });

  it("does not render the tags container when tags is undefined (no tags property)", () => {
    const video = makeVideo();
    // Ensure tags is not set at all
    delete video.tags;
    const { container } = render(<VideoCard video={video} />);
    const tagsRow = container.querySelector(".videoTags");
    expect(tagsRow).toBeNull();
  });

  it("does render the tags container when at least one tag is provided", () => {
    const { container } = render(
      <VideoCard video={makeVideo({ tags: ["react"] })} />
    );
    // Positive control: tags row must be present when tags exist
    const tagsRow = container.querySelector(".videoTags");
    expect(tagsRow).not.toBeNull();
  });

  it("omitted tags row leaves no empty space — no child elements rendered for empty tags", () => {
    const { container } = render(<VideoCard video={makeVideo({ tags: [] })} />);
    // No <span> with a tag pill class should exist when tags is empty
    const tagPills = container.querySelectorAll(".tagPill");
    expect(tagPills.length).toBe(0);
    // No overflow indicator either
    const overflowIndicators = container.querySelectorAll(".tagOverflow");
    expect(overflowIndicators.length).toBe(0);
  });
});
