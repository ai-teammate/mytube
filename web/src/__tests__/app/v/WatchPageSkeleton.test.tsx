/**
 * Unit tests for WatchPageSkeleton
 */
import React from "react";
import { render, screen } from "@testing-library/react";
import WatchPageSkeleton from "@/app/v/[id]/WatchPageSkeleton";

describe("WatchPageSkeleton", () => {
  it("renders a main element", () => {
    render(<WatchPageSkeleton />);
    expect(screen.getByRole("main")).toBeInTheDocument();
  });

  it("renders an aside element for the sidebar", () => {
    render(<WatchPageSkeleton />);
    expect(screen.getByRole("complementary")).toBeInTheDocument();
  });

  it("renders skeleton placeholder elements", () => {
    const { container } = render(<WatchPageSkeleton />);
    // Multiple aria-hidden skeleton divs should be present
    const hiddenEls = container.querySelectorAll('[aria-hidden="true"]');
    expect(hiddenEls.length).toBeGreaterThan(0);
  });

  it("does not render any real video content", () => {
    render(<WatchPageSkeleton />);
    // No heading for video title
    expect(screen.queryByRole("heading")).not.toBeInTheDocument();
  });
});
