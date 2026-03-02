/**
 * Unit tests for src/components/SiteHeader.tsx
 */
import React from "react";
import { render, screen, fireEvent } from "@testing-library/react";

// ─── Mock next/navigation ─────────────────────────────────────────────────────
const mockPush = jest.fn();
jest.mock("next/navigation", () => ({
  useRouter: () => ({
    push: mockPush,
  }),
}));

import SiteHeader from "@/components/SiteHeader";

beforeEach(() => {
  jest.clearAllMocks();
});

describe("SiteHeader", () => {
  it("renders the brand link", () => {
    render(<SiteHeader />);
    const link = screen.getByRole("link", { name: /mytube/i });
    expect(link).toHaveAttribute("href", "/");
  });

  it("renders the search input", () => {
    render(<SiteHeader />);
    expect(screen.getByRole("searchbox", { name: /search query/i })).toBeInTheDocument();
  });

  it("renders the search button", () => {
    render(<SiteHeader />);
    expect(screen.getByRole("button", { name: /submit search/i })).toBeInTheDocument();
  });

  it("submits the search form and navigates to /search?q=", () => {
    render(<SiteHeader />);
    const input = screen.getByRole("searchbox");
    fireEvent.change(input, { target: { value: "go tutorial" } });
    fireEvent.submit(screen.getByRole("search"));

    expect(mockPush).toHaveBeenCalledWith(
      "/search?q=go%20tutorial"
    );
  });

  it("does not navigate when query is empty", () => {
    render(<SiteHeader />);
    fireEvent.submit(screen.getByRole("search"));
    expect(mockPush).not.toHaveBeenCalled();
  });

  it("does not navigate when query is whitespace only", () => {
    render(<SiteHeader />);
    const input = screen.getByRole("searchbox");
    fireEvent.change(input, { target: { value: "   " } });
    fireEvent.submit(screen.getByRole("search"));
    expect(mockPush).not.toHaveBeenCalled();
  });

  it("URL-encodes the search query", () => {
    render(<SiteHeader />);
    const input = screen.getByRole("searchbox");
    fireEvent.change(input, { target: { value: "hello world" } });
    fireEvent.submit(screen.getByRole("search"));
    expect(mockPush).toHaveBeenCalledWith("/search?q=hello%20world");
  });
});
