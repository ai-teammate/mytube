/**
 * Unit tests for src/components/SiteFooter.tsx
 */
import React from "react";
import { render, screen } from "@testing-library/react";

// ─── Mock next/link ───────────────────────────────────────────────────────────
jest.mock("next/link", () => {
  const Link = ({ href, children, ...rest }: {
    href: string;
    children: React.ReactNode;
    [key: string]: unknown;
  }) => <a href={href} {...rest}>{children}</a>;
  Link.displayName = "Link";
  return Link;
});

import SiteFooter from "@/components/SiteFooter";

describe("SiteFooter", () => {
  it("renders the copyright notice with the current year", () => {
    render(<SiteFooter />);
    const year = new Date().getFullYear().toString();
    expect(screen.getByText(new RegExp(year))).toBeInTheDocument();
    expect(screen.getByText(/mytube/i)).toBeInTheDocument();
  });

  it("renders the Terms placeholder link", () => {
    render(<SiteFooter />);
    const link = screen.getByRole("link", { name: /^terms$/i });
    expect(link).toBeInTheDocument();
    expect(link).toHaveAttribute("href", "/terms");
  });

  it("renders the Privacy placeholder link", () => {
    render(<SiteFooter />);
    const link = screen.getByRole("link", { name: /^privacy$/i });
    expect(link).toBeInTheDocument();
    expect(link).toHaveAttribute("href", "/privacy");
  });

  it("renders the footer navigation landmark", () => {
    render(<SiteFooter />);
    expect(screen.getByRole("navigation", { name: /footer navigation/i })).toBeInTheDocument();
  });

  it("renders a footer element", () => {
    const { container } = render(<SiteFooter />);
    expect(container.querySelector("footer")).toBeInTheDocument();
  });
});

describe("SiteFooter — design tokens", () => {
  it("footer element uses var(--bg-card) background token", () => {
    const { container } = render(<SiteFooter />);
    const footer = container.querySelector("footer") as HTMLElement;
    expect(footer.style.background).toContain("var(--bg-card)");
  });

  it("footer element uses var(--border-light) border-top token", () => {
    const { container } = render(<SiteFooter />);
    const footer = container.querySelector("footer") as HTMLElement;
    expect(footer.style.borderTop).toContain("var(--border-light)");
  });

  it("footer has horizontal padding class px-10", () => {
    const { container } = render(<SiteFooter />);
    const footer = container.querySelector("footer") as HTMLElement;
    expect(footer.className).toContain("px-10");
  });

  it("copyright paragraph uses text-[13px] class", () => {
    render(<SiteFooter />);
    const copyright = screen.getByText(/all rights reserved/i).closest("p") as HTMLElement;
    expect(copyright.className).toContain("text-[13px]");
  });

  it("copyright paragraph uses var(--text-subtle) colour token", () => {
    render(<SiteFooter />);
    const copyright = screen.getByText(/all rights reserved/i).closest("p") as HTMLElement;
    expect(copyright.style.color).toContain("var(--text-subtle)");
  });

  it("Terms link uses var(--text-subtle) colour token", () => {
    render(<SiteFooter />);
    const termsLink = screen.getByRole("link", { name: /^terms$/i }) as HTMLElement;
    expect(termsLink.style.color).toContain("var(--text-subtle)");
  });

  it("Privacy link uses var(--text-subtle) colour token", () => {
    render(<SiteFooter />);
    const privacyLink = screen.getByRole("link", { name: /^privacy$/i }) as HTMLElement;
    expect(privacyLink.style.color).toContain("var(--text-subtle)");
  });
});
