/**
 * Unit tests for src/components/SiteFooter.tsx
 */
import React from "react";
import { render, screen } from "@testing-library/react";

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
