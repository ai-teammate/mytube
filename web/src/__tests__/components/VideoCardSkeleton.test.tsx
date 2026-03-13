/**
 * Unit tests for src/components/VideoCardSkeleton.tsx
 */
import React from "react";
import { render, screen } from "@testing-library/react";
import VideoCardSkeleton from "@/components/VideoCardSkeleton";

describe("VideoCardSkeleton", () => {
  it("renders the default count of 8 skeleton cards", () => {
    const { container } = render(
      <div>
        <VideoCardSkeleton />
      </div>
    );
    // Each skeleton card is aria-hidden="true"
    const cards = container.querySelectorAll('[aria-hidden="true"]');
    // 8 cards, each containing 4 Skeleton divs = at least 8 aria-hidden elements at top level
    // We check we have exactly 8 card elements (the top-level card divs)
    // Count direct children of wrapper div
    expect(container.firstChild?.childNodes.length).toBe(8);
  });

  it("renders the specified count of skeleton cards", () => {
    const { container } = render(
      <div>
        <VideoCardSkeleton count={4} />
      </div>
    );
    expect(container.firstChild?.childNodes.length).toBe(4);
  });

  it("renders 1 skeleton card when count is 1", () => {
    const { container } = render(
      <div>
        <VideoCardSkeleton count={1} />
      </div>
    );
    expect(container.firstChild?.childNodes.length).toBe(1);
  });

  it("renders skeleton cards with aria-hidden for accessibility", () => {
    const { container } = render(
      <div>
        <VideoCardSkeleton count={2} />
      </div>
    );
    const hiddenCards = container.querySelectorAll('[aria-hidden="true"]');
    // Each card is aria-hidden, plus each Skeleton inside is also aria-hidden
    // Ensure the card-level elements exist
    expect(hiddenCards.length).toBeGreaterThanOrEqual(2);
  });

  it("renders 6 cards when count is 6", () => {
    const { container } = render(
      <div>
        <VideoCardSkeleton count={6} />
      </div>
    );
    expect(container.firstChild?.childNodes.length).toBe(6);
  });
});
