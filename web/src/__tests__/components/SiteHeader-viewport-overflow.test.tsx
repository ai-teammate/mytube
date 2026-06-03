/**
 * Regression tests for MYTUBE-567 — SiteHeader logo text overflow on mobile
 *
 * Root cause: logo text block (MYTUBE + subtitle) is always visible with no
 * mobile hide class, causing the header to require ~413px on a 375px viewport.
 *
 * Fix: logo text block must use `hidden sm:flex` so it is hidden on mobile and
 * only appears at sm (≥640px) breakpoints.
 */
import React from "react";
import { render, screen } from "@testing-library/react";

jest.mock("next/navigation", () => ({
  useRouter: () => ({ push: jest.fn(), replace: jest.fn() }),
}));

jest.mock("next/link", () => {
  const Link = ({
    href,
    children,
    ...rest
  }: {
    href: string;
    children: React.ReactNode;
    [key: string]: unknown;
  }) => (
    <a href={href} {...rest}>
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

describe("SiteHeader — mobile viewport overflow fix (MYTUBE-567)", () => {
  it("logo text container is hidden on mobile (has 'hidden' class) and shown at sm+ (has 'sm:flex')", () => {
    const { container } = render(<SiteHeader />);
    const logoLink = screen.getByRole("link", { name: /mytube/i });

    // The text block wrapping "MYTUBE" and the subtitle must be a direct child div
    // of the logo link that carries both 'hidden' and 'sm:flex'.
    const textBlock = logoLink.querySelector("div");
    expect(textBlock).not.toBeNull();

    const classes = textBlock!.className.split(/\s+/);
    expect(classes).toContain("hidden");
    expect(classes).toContain("sm:flex");
  });

  it("logo link does NOT use 'flex flex-col' directly on the text div (would always show on mobile)", () => {
    const { container } = render(<SiteHeader />);
    const logoLink = screen.getByRole("link", { name: /mytube/i });

    const textBlock = logoLink.querySelector("div");
    expect(textBlock).not.toBeNull();

    const classes = textBlock!.className.split(/\s+/);
    // Must NOT have bare 'flex' without the mobile-hide 'hidden' guard
    // (i.e. if it has 'flex' but no 'hidden', the layout overflows on mobile)
    if (classes.includes("flex")) {
      expect(classes).toContain("hidden");
    }
  });

  it("utility area (theme toggle + auth) has shrink-0 but is within budget at mobile with logo text hidden", () => {
    const { container } = render(<SiteHeader />);
    const header = container.querySelector("header");
    expect(header).not.toBeNull();

    // The utility area must still have shrink-0 (auth items must not be squished)
    const utilityDiv = header!.querySelector("div.shrink-0");
    expect(utilityDiv).not.toBeNull();
  });

  it("logo link has an aria-label so screen readers can identify it when text is visually hidden on mobile", () => {
    render(<SiteHeader />);
    // aria-label provides an accessible name regardless of CSS visibility
    const logoLink = screen.getByRole("link", { name: /mytube/i });
    expect(logoLink).toHaveAttribute("aria-label", "MYTUBE — Personal Video Portal");
  });
});
