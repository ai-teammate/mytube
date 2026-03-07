/**
 * Unit tests for src/components/SiteHeader.tsx
 */
import React from "react";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

// ─── Mock next/navigation ─────────────────────────────────────────────────────
const mockPush = jest.fn();
const mockReplace = jest.fn();

jest.mock("next/navigation", () => ({
  useRouter: () => ({
    push: mockPush,
    replace: mockReplace,
  }),
}));

// ─── Mock next/link ───────────────────────────────────────────────────────────
jest.mock("next/link", () => {
  const Link = ({ href, children, onClick, ...rest }: {
    href: string;
    children: React.ReactNode;
    onClick?: () => void;
    [key: string]: unknown;
  }) => <a href={href} onClick={onClick} {...rest}>{children}</a>;
  Link.displayName = "Link";
  return Link;
});

// ─── Mock AuthContext ─────────────────────────────────────────────────────────
let mockUser: { email: string; displayName: string | null } | null = null;
let mockLoading = false;
const mockSignOut = jest.fn().mockResolvedValue(undefined);

jest.mock("@/context/AuthContext", () => ({
  useAuth: () => ({ user: mockUser, loading: mockLoading, signOut: mockSignOut }),
}));

import SiteHeader from "@/components/SiteHeader";

beforeEach(() => {
  jest.clearAllMocks();
  mockUser = null;
  mockLoading = false;
});

describe("SiteHeader — search", () => {
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

describe("SiteHeader — unauthenticated", () => {
  it("shows Sign in link when not loading and no user", () => {
    render(<SiteHeader />);
    expect(screen.getByRole("link", { name: /sign in/i })).toHaveAttribute(
      "href",
      "/login"
    );
  });

  it("does not show user menu button when unauthenticated", () => {
    render(<SiteHeader />);
    expect(screen.queryByRole("button", { name: /user menu/i })).not.toBeInTheDocument();
  });

  it("renders nothing for nav when loading", () => {
    mockLoading = true;
    render(<SiteHeader />);
    expect(screen.queryByRole("link", { name: /sign in/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /user menu/i })).not.toBeInTheDocument();
  });
});

describe("SiteHeader — authenticated", () => {
  beforeEach(() => {
    mockUser = { email: "alice@example.com", displayName: "Alice" };
  });

  it("shows the user menu button when authenticated", () => {
    render(<SiteHeader />);
    expect(screen.getByRole("button", { name: /user menu/i })).toBeInTheDocument();
  });

  it("does not show Sign in link when authenticated", () => {
    render(<SiteHeader />);
    expect(screen.queryByRole("link", { name: /sign in/i })).not.toBeInTheDocument();
  });

  it("shows displayName in avatar button", () => {
    render(<SiteHeader />);
    const btn = screen.getByRole("button", { name: /user menu/i });
    // First letter of displayName
    expect(btn.textContent).toContain("A");
  });

  it("falls back to email when displayName is null", () => {
    mockUser = { email: "bob@example.com", displayName: null };
    render(<SiteHeader />);
    const btn = screen.getByRole("button", { name: /user menu/i });
    expect(btn.textContent).toContain("b");
  });

  it("opens dropdown menu when user menu button is clicked", async () => {
    const user = userEvent.setup();
    render(<SiteHeader />);
    await user.click(screen.getByRole("button", { name: /user menu/i }));
    expect(screen.getByRole("menu")).toBeInTheDocument();
  });

  it("dropdown contains Upload, My Videos, Account Settings links", async () => {
    const user = userEvent.setup();
    render(<SiteHeader />);
    await user.click(screen.getByRole("button", { name: /user menu/i }));
    expect(screen.getByRole("menuitem", { name: /upload/i })).toHaveAttribute("href", "/upload");
    expect(screen.getByRole("menuitem", { name: /my videos/i })).toHaveAttribute("href", "/dashboard");
    expect(screen.getByRole("menuitem", { name: /account settings/i })).toHaveAttribute("href", "/settings");
  });

  it("dropdown contains Sign out button", async () => {
    const user = userEvent.setup();
    render(<SiteHeader />);
    await user.click(screen.getByRole("button", { name: /user menu/i }));
    expect(screen.getByRole("menuitem", { name: /sign out/i })).toBeInTheDocument();
  });

  it("closes dropdown when a menu link is clicked", async () => {
    const user = userEvent.setup();
    render(<SiteHeader />);
    await user.click(screen.getByRole("button", { name: /user menu/i }));
    await user.click(screen.getByRole("menuitem", { name: /upload/i }));
    expect(screen.queryByRole("menu")).not.toBeInTheDocument();
  });

  it("calls signOut and redirects to /login on sign-out click", async () => {
    const user = userEvent.setup();
    render(<SiteHeader />);
    await user.click(screen.getByRole("button", { name: /user menu/i }));
    await user.click(screen.getByRole("menuitem", { name: /sign out/i }));
    expect(mockSignOut).toHaveBeenCalledTimes(1);
    await waitFor(() => {
      expect(mockReplace).toHaveBeenCalledWith("/login");
    });
  });

  it("menu is not visible before user menu button is clicked", () => {
    render(<SiteHeader />);
    expect(screen.queryByRole("menu")).not.toBeInTheDocument();
  });

  it("toggles menu closed when button clicked again", async () => {
    const user = userEvent.setup();
    render(<SiteHeader />);
    await user.click(screen.getByRole("button", { name: /user menu/i }));
    expect(screen.getByRole("menu")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /user menu/i }));
    expect(screen.queryByRole("menu")).not.toBeInTheDocument();
  });

  it("closes dropdown when clicking outside the menu container", async () => {
    const user = userEvent.setup();
    render(<SiteHeader />);
    await user.click(screen.getByRole("button", { name: /user menu/i }));
    expect(screen.getByRole("menu")).toBeInTheDocument();
    fireEvent.mouseDown(document.body);
    expect(screen.queryByRole("menu")).not.toBeInTheDocument();
  });

  it("closes dropdown when Escape key is pressed", async () => {
    const user = userEvent.setup();
    render(<SiteHeader />);
    await user.click(screen.getByRole("button", { name: /user menu/i }));
    expect(screen.getByRole("menu")).toBeInTheDocument();
    fireEvent.keyDown(document, { key: "Escape" });
    expect(screen.queryByRole("menu")).not.toBeInTheDocument();
  });
});
