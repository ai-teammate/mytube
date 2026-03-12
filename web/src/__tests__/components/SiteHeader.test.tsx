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
let mockAuthError = false;
const mockSignOut = jest.fn().mockResolvedValue(undefined);

jest.mock("@/context/AuthContext", () => ({
  useAuth: () => ({ user: mockUser, loading: mockLoading, authError: mockAuthError, signOut: mockSignOut }),
}));

// ─── Mock ThemeContext ────────────────────────────────────────────────────────
let mockTheme: "light" | "dark" = "light";
const mockToggleTheme = jest.fn();

jest.mock("@/context/ThemeContext", () => ({
  useTheme: () => ({ theme: mockTheme, toggleTheme: mockToggleTheme }),
}));

import SiteHeader from "@/components/SiteHeader";

beforeEach(() => {
  jest.clearAllMocks();
  mockUser = null;
  mockLoading = false;
  mockAuthError = false;
  mockTheme = "light";
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

describe("SiteHeader — auth error", () => {
  beforeEach(() => {
    mockAuthError = true;
  });

  it("shows auth unavailability message when authError is true", () => {
    render(<SiteHeader />);
    expect(screen.getByRole("alert")).toHaveTextContent(
      "Authentication services are currently unavailable"
    );
  });

  it("does not show Sign in link when authError is true", () => {
    render(<SiteHeader />);
    expect(screen.queryByRole("link", { name: /sign in/i })).not.toBeInTheDocument();
  });

  it("does not show user menu button when authError is true", () => {
    render(<SiteHeader />);
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

describe("SiteHeader — branded logo", () => {
  it("renders a link to / containing brand name MYTUBE", () => {
    render(<SiteHeader />);
    const logoLink = screen.getByRole("link", { name: /mytube/i });
    expect(logoLink).toHaveAttribute("href", "/");
  });

  it("renders MYTUBE heading text", () => {
    render(<SiteHeader />);
    expect(screen.getByText("MYTUBE")).toBeInTheDocument();
  });

  it("renders the logo subtitle 'Personal Video Portal'", () => {
    render(<SiteHeader />);
    expect(screen.getByText(/personal video portal/i)).toBeInTheDocument();
  });

  it("renders the LogoIcon SVG inside the logo link", () => {
    const { container } = render(<SiteHeader />);
    const logoLink = screen.getByRole("link", { name: /mytube/i });
    expect(logoLink.querySelector("svg")).toBeInTheDocument();
  });
});

describe("SiteHeader — nav links", () => {
  it("renders the Home nav link pointing to /", () => {
    render(<SiteHeader />);
    // May have multiple links to "/" (logo + Home); find the one with text "Home"
    const homeLinks = screen.getAllByRole("link", { name: /^home$/i });
    expect(homeLinks.length).toBeGreaterThanOrEqual(1);
    expect(homeLinks[0]).toHaveAttribute("href", "/");
  });

  it("renders the My Videos nav link when unauthenticated, pointing to login redirect", () => {
    render(<SiteHeader />);
    // Nav My Videos (not the dropdown menuitem which only appears after click)
    const navMyVideos = screen.getByRole("link", { name: /^my videos$/i });
    expect(navMyVideos).toHaveAttribute("href", "/login?next=/dashboard");
  });

  it("renders the My Videos nav link when authenticated, pointing to /dashboard", () => {
    mockUser = { email: "alice@example.com", displayName: "Alice" };
    render(<SiteHeader />);
    // The nav link (not the dropdown menuitem)
    const allMyVideosLinks = screen.getAllByRole("link", { name: /my videos/i });
    // At least one link (nav) with href /dashboard
    const navLink = allMyVideosLinks.find((l) => l.getAttribute("href") === "/dashboard");
    expect(navLink).toBeInTheDocument();
  });
});

describe("SiteHeader — theme toggle", () => {
  it("renders the theme toggle button", () => {
    render(<SiteHeader />);
    expect(screen.getByRole("button", { name: /switch to dark mode/i })).toBeInTheDocument();
  });

  it("shows MoonIcon (switch to dark) when theme is light", () => {
    mockTheme = "light";
    const { container } = render(<SiteHeader />);
    const toggleBtn = screen.getByRole("button", { name: /switch to dark mode/i });
    expect(toggleBtn.querySelector("svg")).toBeInTheDocument();
  });

  it("shows SunIcon (switch to light) when theme is dark", () => {
    mockTheme = "dark";
    render(<SiteHeader />);
    expect(screen.getByRole("button", { name: /switch to light mode/i })).toBeInTheDocument();
  });

  it("calls toggleTheme when the theme toggle button is clicked", async () => {
    const user = userEvent.setup();
    render(<SiteHeader />);
    await user.click(screen.getByRole("button", { name: /switch to (dark|light) mode/i }));
    expect(mockToggleTheme).toHaveBeenCalledTimes(1);
  });
});

describe("SiteHeader — login button styling", () => {
  it("renders the login button as a link to /login", () => {
    render(<SiteHeader />);
    const signInLink = screen.getByRole("link", { name: /sign in/i });
    expect(signInLink).toHaveAttribute("href", "/login");
  });

  it("login link has font-semibold class (font-weight 600)", () => {
    render(<SiteHeader />);
    const signInLink = screen.getByRole("link", { name: /sign in/i });
    expect(signInLink.className).toContain("font-semibold");
  });

  it("login link has rounded-full class (pill shape)", () => {
    render(<SiteHeader />);
    const signInLink = screen.getByRole("link", { name: /sign in/i });
    expect(signInLink.className).toContain("rounded-full");
  });
});

describe("SiteHeader — avatar gradient", () => {
  it("authenticated avatar uses --gradient-hero token", () => {
    mockUser = { email: "alice@example.com", displayName: "Alice" };
    render(<SiteHeader />);
    const menuBtn = screen.getByRole("button", { name: /user menu/i });
    const avatarSpan = menuBtn.querySelector("span[aria-hidden='true']") as HTMLElement;
    // JSDOM doesn't compute CSS vars; check raw style attribute
    expect(avatarSpan?.getAttribute("style")).toContain("var(--gradient-hero)");
  });
});
