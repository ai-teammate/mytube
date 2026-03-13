/**
 * Unit tests for MYTUBE-566 — SiteHeader hamburger menu on mobile
 *
 * Verifies that a hamburger toggle button is present and functional,
 * allowing mobile users (viewport ≤640px) to access navigation links.
 */
import React from "react";
import { render, screen, fireEvent, act } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

jest.mock("next/navigation", () => ({
  useRouter: () => ({ push: jest.fn(), replace: jest.fn() }),
}));

jest.mock("next/link", () => {
  const Link = ({
    href,
    children,
    onClick,
    ...rest
  }: {
    href: string;
    children: React.ReactNode;
    onClick?: () => void;
    [key: string]: unknown;
  }) => (
    <a href={href} onClick={onClick} {...rest}>
      {children}
    </a>
  );
  Link.displayName = "Link";
  return Link;
});

jest.mock("@/context/AuthContext", () => ({
  useAuth: () => ({
    user: null,
    loading: false,
    authError: false,
    signOut: jest.fn(),
  }),
}));

jest.mock("@/context/ThemeContext", () => ({
  useTheme: () => ({ theme: "light", toggleTheme: jest.fn() }),
}));

import SiteHeader from "@/components/SiteHeader";

describe("SiteHeader — hamburger menu (MYTUBE-566)", () => {
  it("renders a hamburger/mobile-menu toggle button in the header", () => {
    render(<SiteHeader />);
    // Must have a button with aria-label containing 'menu', 'nav', or 'hamburger'
    const hamburger = screen.getByRole("button", {
      name: /open navigation menu|hamburger|mobile menu|nav/i,
    });
    expect(hamburger).toBeInTheDocument();
  });

  it("hamburger button has sm:hidden class so it is only visible on mobile", () => {
    render(<SiteHeader />);
    const hamburger = screen.getByRole("button", {
      name: /open navigation menu|hamburger|mobile menu|nav/i,
    });
    expect(hamburger.className).toMatch(/sm:hidden/);
  });

  it("mobile nav is not visible before hamburger is clicked", () => {
    render(<SiteHeader />);
    // Mobile nav panel should be hidden/absent initially
    expect(screen.queryByRole("navigation", { name: /mobile navigation/i })).not.toBeInTheDocument();
  });

  it("clicking hamburger expands mobile nav showing Home link", async () => {
    const user = userEvent.setup();
    render(<SiteHeader />);
    const hamburger = screen.getByRole("button", {
      name: /open navigation menu|hamburger|mobile menu|nav/i,
    });
    await user.click(hamburger);
    const mobileNav = screen.getByRole("navigation", { name: /mobile navigation/i });
    expect(mobileNav).toBeInTheDocument();
    const homeLinks = screen.getAllByRole("link", { name: /^home$/i });
    // At least one visible in the mobile nav
    expect(homeLinks.length).toBeGreaterThanOrEqual(1);
  });

  it("clicking hamburger expands mobile nav showing My Videos link", async () => {
    const user = userEvent.setup();
    render(<SiteHeader />);
    const hamburger = screen.getByRole("button", {
      name: /open navigation menu|hamburger|mobile menu|nav/i,
    });
    await user.click(hamburger);
    const mobileNav = screen.getByRole("navigation", { name: /mobile navigation/i });
    expect(mobileNav).toBeInTheDocument();
    // For unauthenticated user, My Videos should redirect to login
    const myVideosLinks = screen.getAllByRole("link", { name: /^my videos$/i });
    expect(myVideosLinks.length).toBeGreaterThanOrEqual(1);
  });

  it("clicking hamburger again closes the mobile nav", async () => {
    const user = userEvent.setup();
    render(<SiteHeader />);
    const hamburger = screen.getByRole("button", {
      name: /open navigation menu|hamburger|mobile menu|nav/i,
    });
    await user.click(hamburger);
    expect(screen.getByRole("navigation", { name: /mobile navigation/i })).toBeInTheDocument();
    await user.click(hamburger);
    expect(screen.queryByRole("navigation", { name: /mobile navigation/i })).not.toBeInTheDocument();
  });

  it("clicking a mobile nav link closes the mobile menu", async () => {
    const user = userEvent.setup();
    render(<SiteHeader />);
    const hamburger = screen.getByRole("button", {
      name: /open navigation menu|hamburger|mobile menu|nav/i,
    });
    await user.click(hamburger);
    expect(screen.getByRole("navigation", { name: /mobile navigation/i })).toBeInTheDocument();
    // Click the Home link in the mobile nav
    const homeLinks = screen.getAllByRole("link", { name: /^home$/i });
    await user.click(homeLinks[homeLinks.length - 1]);
    expect(screen.queryByRole("navigation", { name: /mobile navigation/i })).not.toBeInTheDocument();
  });

  it("hamburger aria-label updates to reflect open state", async () => {
    const user = userEvent.setup();
    render(<SiteHeader />);
    const hamburger = screen.getByRole("button", {
      name: /open navigation menu|hamburger|mobile menu|nav/i,
    });
    await user.click(hamburger);
    // When open, button should say "close" or similar
    expect(
      screen.getByRole("button", {
        name: /close navigation menu|close menu|close nav/i,
      })
    ).toBeInTheDocument();
  });

  it("Escape key closes the mobile nav (WCAG 2.1 SC 2.1.1)", async () => {
    const user = userEvent.setup();
    render(<SiteHeader />);
    await user.click(
      screen.getByRole("button", { name: /open navigation menu/i })
    );
    expect(
      screen.getByRole("navigation", { name: /mobile navigation/i })
    ).toBeInTheDocument();
    await user.keyboard("{Escape}");
    expect(
      screen.queryByRole("navigation", { name: /mobile navigation/i })
    ).not.toBeInTheDocument();
  });

  it("clicking outside the mobile nav closes it", async () => {
    const user = userEvent.setup();
    render(<SiteHeader />);
    await user.click(
      screen.getByRole("button", { name: /open navigation menu/i })
    );
    expect(
      screen.getByRole("navigation", { name: /mobile navigation/i })
    ).toBeInTheDocument();
    fireEvent.mouseDown(document.body);
    expect(
      screen.queryByRole("navigation", { name: /mobile navigation/i })
    ).not.toBeInTheDocument();
  });

  it("resizing viewport to ≥640px closes the mobile nav", async () => {
    const originalInnerWidth = window.innerWidth;
    const user = userEvent.setup();
    render(<SiteHeader />);
    await user.click(
      screen.getByRole("button", { name: /open navigation menu/i })
    );
    expect(
      screen.getByRole("navigation", { name: /mobile navigation/i })
    ).toBeInTheDocument();
    Object.defineProperty(window, "innerWidth", {
      writable: true,
      configurable: true,
      value: 640,
    });
    act(() => {
      fireEvent(window, new Event("resize"));
    });
    expect(
      screen.queryByRole("navigation", { name: /mobile navigation/i })
    ).not.toBeInTheDocument();
    Object.defineProperty(window, "innerWidth", {
      writable: true,
      configurable: true,
      value: originalInnerWidth,
    });
  });
});
