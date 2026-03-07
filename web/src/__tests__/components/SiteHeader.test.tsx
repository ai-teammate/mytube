/**
 * Unit tests for src/components/SiteHeader.tsx
 */
import React from "react";
import { render, screen, fireEvent } from "@testing-library/react";

// ─── Mock next/navigation ─────────────────────────────────────────────────────
const mockPush = jest.fn();
let mockPathname = "/";

jest.mock("next/navigation", () => ({
  useRouter: () => ({
    push: mockPush,
  }),
  usePathname: () => mockPathname,
}));

// ─── Mock AuthContext ─────────────────────────────────────────────────────────
let mockUser: { email: string } | null = null;
const mockSignOut = jest.fn();

jest.mock("@/context/AuthContext", () => ({
  useAuth: () => ({
    user: mockUser,
    signOut: mockSignOut,
  }),
}));

import SiteHeader from "@/components/SiteHeader";

beforeEach(() => {
  jest.clearAllMocks();
  mockUser = null;
  mockPathname = "/";
});

describe("SiteHeader", () => {
  // ── Logo ────────────────────────────────────────────────────────────────────

  it("renders the brand link", () => {
    render(<SiteHeader />);
    const link = screen.getByRole("link", { name: /mytube/i });
    expect(link).toHaveAttribute("href", "/");
  });

  // ── Search form ─────────────────────────────────────────────────────────────

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

  // ── Unauthenticated nav ──────────────────────────────────────────────────────

  it("shows Home nav link when unauthenticated", () => {
    render(<SiteHeader />);
    // Home appears in desktop nav (and not in the mobile menu since it's closed)
    const homeLinks = screen.getAllByRole("link", { name: /^home$/i });
    expect(homeLinks.length).toBeGreaterThanOrEqual(1);
  });

  it("does not show Upload link when unauthenticated", () => {
    render(<SiteHeader />);
    expect(screen.queryByRole("link", { name: /^upload$/i })).not.toBeInTheDocument();
  });

  it("does not show My Videos link when unauthenticated", () => {
    render(<SiteHeader />);
    expect(screen.queryByRole("link", { name: /my videos/i })).not.toBeInTheDocument();
  });

  it("does not show Playlists link when unauthenticated", () => {
    render(<SiteHeader />);
    expect(screen.queryByRole("link", { name: /playlists/i })).not.toBeInTheDocument();
  });

  it("does not show Sign out button when unauthenticated", () => {
    render(<SiteHeader />);
    expect(screen.queryByRole("button", { name: /sign out/i })).not.toBeInTheDocument();
  });

  // ── Authenticated nav ────────────────────────────────────────────────────────

  it("shows Upload link when authenticated", () => {
    mockUser = { email: "alice@example.com" };
    render(<SiteHeader />);
    expect(screen.getAllByRole("link", { name: /^upload$/i }).length).toBeGreaterThanOrEqual(1);
  });

  it("Upload link points to /upload", () => {
    mockUser = { email: "alice@example.com" };
    render(<SiteHeader />);
    const links = screen.getAllByRole("link", { name: /^upload$/i });
    expect(links[0]).toHaveAttribute("href", "/upload");
  });

  it("shows My Videos link when authenticated", () => {
    mockUser = { email: "alice@example.com" };
    render(<SiteHeader />);
    expect(screen.getAllByRole("link", { name: /my videos/i }).length).toBeGreaterThanOrEqual(1);
  });

  it("My Videos link points to /dashboard", () => {
    mockUser = { email: "alice@example.com" };
    render(<SiteHeader />);
    const links = screen.getAllByRole("link", { name: /my videos/i });
    expect(links[0]).toHaveAttribute("href", "/dashboard");
  });

  it("shows Playlists link when authenticated", () => {
    mockUser = { email: "alice@example.com" };
    render(<SiteHeader />);
    expect(screen.getAllByRole("link", { name: /playlists/i }).length).toBeGreaterThanOrEqual(1);
  });

  it("Playlists link points to /dashboard", () => {
    mockUser = { email: "alice@example.com" };
    render(<SiteHeader />);
    const links = screen.getAllByRole("link", { name: /playlists/i });
    expect(links[0]).toHaveAttribute("href", "/dashboard");
  });

  it("shows Sign out button when authenticated", () => {
    mockUser = { email: "alice@example.com" };
    render(<SiteHeader />);
    expect(screen.getAllByRole("button", { name: /sign out/i }).length).toBeGreaterThanOrEqual(1);
  });

  it("calls signOut when Sign out button is clicked (desktop)", () => {
    mockUser = { email: "alice@example.com" };
    render(<SiteHeader />);
    // The desktop sign out button is the first one
    const buttons = screen.getAllByRole("button", { name: /sign out/i });
    fireEvent.click(buttons[0]);
    expect(mockSignOut).toHaveBeenCalledTimes(1);
  });

  // ── Hamburger menu ───────────────────────────────────────────────────────────

  it("renders the hamburger button", () => {
    render(<SiteHeader />);
    expect(screen.getByRole("button", { name: /open menu/i })).toBeInTheDocument();
  });

  it("mobile menu is not visible by default", () => {
    render(<SiteHeader />);
    expect(screen.queryByRole("navigation", { name: /mobile navigation/i })).not.toBeInTheDocument();
  });

  it("opens mobile menu when hamburger is clicked", () => {
    render(<SiteHeader />);
    fireEvent.click(screen.getByRole("button", { name: /open menu/i }));
    expect(screen.getByRole("navigation", { name: /mobile navigation/i })).toBeInTheDocument();
  });

  it("shows close button after menu is opened", () => {
    render(<SiteHeader />);
    fireEvent.click(screen.getByRole("button", { name: /open menu/i }));
    expect(screen.getByRole("button", { name: /close menu/i })).toBeInTheDocument();
  });

  it("closes mobile menu when close button is clicked", () => {
    render(<SiteHeader />);
    fireEvent.click(screen.getByRole("button", { name: /open menu/i }));
    fireEvent.click(screen.getByRole("button", { name: /close menu/i }));
    expect(screen.queryByRole("navigation", { name: /mobile navigation/i })).not.toBeInTheDocument();
  });

  it("mobile menu shows Home link for unauthenticated users", () => {
    render(<SiteHeader />);
    fireEvent.click(screen.getByRole("button", { name: /open menu/i }));
    const nav = screen.getByRole("navigation", { name: /mobile navigation/i });
    expect(nav.querySelector('a[href="/"]')).toBeInTheDocument();
  });

  it("mobile menu shows auth links when authenticated", () => {
    mockUser = { email: "alice@example.com" };
    render(<SiteHeader />);
    fireEvent.click(screen.getByRole("button", { name: /open menu/i }));
    const nav = screen.getByRole("navigation", { name: /mobile navigation/i });
    expect(nav.querySelector('a[href="/upload"]')).toBeInTheDocument();
    expect(nav.querySelector('a[href="/dashboard"]')).toBeInTheDocument();
  });

  it("mobile menu does not show auth links when unauthenticated", () => {
    render(<SiteHeader />);
    fireEvent.click(screen.getByRole("button", { name: /open menu/i }));
    const nav = screen.getByRole("navigation", { name: /mobile navigation/i });
    expect(nav.querySelector('a[href="/upload"]')).not.toBeInTheDocument();
  });

  it("mobile menu Sign out button calls signOut and closes menu", () => {
    mockUser = { email: "alice@example.com" };
    render(<SiteHeader />);
    fireEvent.click(screen.getByRole("button", { name: /open menu/i }));
    const nav = screen.getByRole("navigation", { name: /mobile navigation/i });
    const signOutBtn = nav.querySelector("button");
    fireEvent.click(signOutBtn!);
    expect(mockSignOut).toHaveBeenCalledTimes(1);
    expect(screen.queryByRole("navigation", { name: /mobile navigation/i })).not.toBeInTheDocument();
  });

  // ── Active link highlight ────────────────────────────────────────────────────

  it("Home link has active styling when on /", () => {
    mockPathname = "/";
    render(<SiteHeader />);
    const homeLinks = screen.getAllByRole("link", { name: /^home$/i });
    expect(homeLinks[0].className).toContain("text-red-600");
  });

  it("Upload link has active styling when on /upload", () => {
    mockPathname = "/upload";
    mockUser = { email: "alice@example.com" };
    render(<SiteHeader />);
    const uploadLinks = screen.getAllByRole("link", { name: /^upload$/i });
    expect(uploadLinks[0].className).toContain("text-red-600");
  });
});
