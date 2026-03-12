/**
 * Regression tests for MYTUBE-360:
 * "Input text, placeholders and button labels invisible across site"
 *
 * Root cause: globals.css switches --foreground to #ededed in dark mode, but all
 * containers are hardcoded light (bg-white). Tailwind v4 preflight resets
 * input/textarea/select/button to `color: inherit`, so they inherit near-white
 * text on white backgrounds → invisible text.
 *
 * These tests verify that the shared-layer fix is in place:
 *   1. globals.css has an @layer base rule that pins input/textarea/select to an
 *      explicit dark colour (not relying on inherited body colour).
 *   2. The SiteHeader "Search" submit button carries an explicit text-colour class
 *      so it remains legible regardless of the inherited body colour.
 */
import React from "react";
import * as fs from "fs";
import * as path from "path";
import { render, screen } from "@testing-library/react";

// ─── Mocks required to render SiteHeader ─────────────────────────────────────

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
  useAuth: () => ({ user: null, loading: false, signOut: jest.fn() }),
}));

jest.mock("@/context/ThemeContext", () => ({
  useTheme: () => ({ theme: "light", toggleTheme: jest.fn() }),
}));

import SiteHeader from "@/components/SiteHeader";

// ─── 1. globals.css must pin form-element text colour ─────────────────────────

describe("globals.css — form-element text colour (MYTUBE-360)", () => {
  let css: string;

  beforeAll(() => {
    const cssPath = path.resolve(__dirname, "../../app/globals.css");
    css = fs.readFileSync(cssPath, "utf8");
  });

  it("contains an @layer base block", () => {
    expect(css).toMatch(/@layer\s+base\s*\{/);
  });

  it("applies an explicit text colour to input elements inside @layer base", () => {
    // Extract the @layer base block and verify it contains a color rule for input
    const layerBaseMatch = css.match(/@layer\s+base\s*\{([\s\S]*?)\}/);
    expect(layerBaseMatch).not.toBeNull();
    const layerBaseContent = layerBaseMatch![1];

    // The block must target input (and textarea, select) with a color property
    expect(layerBaseContent).toMatch(/input/);
    expect(layerBaseContent).toMatch(/color\s*:/);
  });

  it("applies an explicit text colour to textarea elements inside @layer base", () => {
    const layerBaseMatch = css.match(/@layer\s+base\s*\{([\s\S]*?)\}/);
    const layerBaseContent = layerBaseMatch![1];
    expect(layerBaseContent).toMatch(/textarea/);
  });

  it("applies an explicit text colour to select elements inside @layer base", () => {
    const layerBaseMatch = css.match(/@layer\s+base\s*\{([\s\S]*?)\}/);
    const layerBaseContent = layerBaseMatch![1];
    expect(layerBaseContent).toMatch(/select/);
  });

  it("does NOT rely solely on color:inherit for form elements (would be invisible in dark mode)", () => {
    // The colour value must not be 'inherit' — that would perpetuate the bug
    const layerBaseMatch = css.match(/@layer\s+base\s*\{([\s\S]*?)\}/);
    const layerBaseContent = layerBaseMatch![1];
    // Extract the color rule value — must not be 'inherit'
    const colorRuleMatch = layerBaseContent.match(/color\s*:\s*([^;]+);/);
    expect(colorRuleMatch).not.toBeNull();
    expect(colorRuleMatch![1].trim()).not.toBe("inherit");
  });
});

// ─── 2. SiteHeader "Search" button must carry an explicit text-colour class ───

describe("SiteHeader — Search button text colour (MYTUBE-360)", () => {
  it("has an explicit text-colour Tailwind class so it is visible in dark mode", () => {
    render(<SiteHeader />);

    const searchButton = screen.getByRole("button", { name: /submit search/i });
    // The button must have at least one text-{colour} class; without it the
    // button label inherits near-white in dark mode → invisible on bg-gray-50.
    const hasTextColour = searchButton.className
      .split(" ")
      .some((cls) => /^text-[a-z]/.test(cls) && cls !== "text-sm");

    expect(hasTextColour).toBe(true);
  });
});
