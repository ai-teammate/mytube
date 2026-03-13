/**
 * Regression tests for MYTUBE-536 — SiteHeader mobile layout
 *
 * Verifies that SiteHeader uses responsive Tailwind classes so it renders
 * correctly on narrow (mobile) viewports.
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

describe("SiteHeader — mobile responsive layout (MYTUBE-536)", () => {
  it("header has responsive horizontal padding (px-4 on mobile, px-10 on sm+)", () => {
    const { container } = render(<SiteHeader />);
    const header = container.querySelector("header");
    expect(header).not.toBeNull();
    // Must have small-screen padding class (px-4) instead of only px-10
    expect(header!.className).toContain("px-4");
    // Must also have sm breakpoint override for larger screens
    expect(header!.className).toContain("sm:px-10");
  });

  it("header has responsive gap (gap-3 on mobile, gap-6 on sm+)", () => {
    const { container } = render(<SiteHeader />);
    const header = container.querySelector("header");
    expect(header).not.toBeNull();
    expect(header!.className).toContain("gap-3");
    expect(header!.className).toContain("sm:gap-6");
  });

  it("header does NOT use unconditional px-10 without a mobile override", () => {
    const { container } = render(<SiteHeader />);
    const header = container.querySelector("header");
    expect(header).not.toBeNull();
    // px-10 should only appear as sm:px-10, not as a bare px-10 class
    const classes = header!.className.split(/\s+/);
    expect(classes).not.toContain("px-10");
  });

  it("search form has min-w-0 so it can shrink inside the flex header", () => {
    const { container } = render(<SiteHeader />);
    const form = container.querySelector("form[role='search']");
    expect(form).not.toBeNull();
    expect(form!.className).toContain("min-w-0");
  });

  it("search input has min-w-0 to prevent intrinsic-size overflow in flex row", () => {
    const { container } = render(<SiteHeader />);
    const input = container.querySelector("input[type='search']");
    expect(input).not.toBeNull();
    expect(input!.className).toContain("min-w-0");
  });
});
