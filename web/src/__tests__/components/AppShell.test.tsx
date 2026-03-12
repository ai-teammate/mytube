/**
 * Unit tests for src/components/AppShell.tsx
 */
import React from "react";
import { render, screen } from "@testing-library/react";

// ─── Mock next/navigation ─────────────────────────────────────────────────────
let mockPathname = "/";

jest.mock("next/navigation", () => ({
  usePathname: () => mockPathname,
  useRouter: () => ({ push: jest.fn() }),
}));

// ─── Mock AuthContext ─────────────────────────────────────────────────────────
jest.mock("@/context/AuthContext", () => ({
  useAuth: () => ({
    user: null,
    loading: false,
    authError: false,
    signOut: jest.fn(),
  }),
}));

import AppShell from "@/components/AppShell";

beforeEach(() => {
  jest.clearAllMocks();
  mockPathname = "/";
});

describe("AppShell", () => {
  // ── Non-auth routes — full shell ─────────────────────────────────────────────

  it("renders children on the home page", () => {
    mockPathname = "/";
    render(
      <AppShell>
        <div>Home content</div>
      </AppShell>
    );
    expect(screen.getByText("Home content")).toBeInTheDocument();
  });

  it("renders SiteHeader on the home page", () => {
    mockPathname = "/";
    render(
      <AppShell>
        <div>content</div>
      </AppShell>
    );
    // SiteHeader renders a header element with the brand link
    expect(screen.getByRole("link", { name: /mytube/i })).toBeInTheDocument();
  });

  it("renders SiteFooter on the home page", () => {
    mockPathname = "/";
    render(
      <AppShell>
        <div>content</div>
      </AppShell>
    );
    expect(screen.getByRole("navigation", { name: /footer navigation/i })).toBeInTheDocument();
  });

  it("renders header and footer on /search", () => {
    mockPathname = "/search";
    render(
      <AppShell>
        <div>Search page</div>
      </AppShell>
    );
    expect(screen.getByRole("link", { name: /mytube/i })).toBeInTheDocument();
    expect(screen.getByRole("navigation", { name: /footer navigation/i })).toBeInTheDocument();
  });

  it("renders header and footer on /dashboard", () => {
    mockPathname = "/dashboard";
    render(
      <AppShell>
        <div>Dashboard</div>
      </AppShell>
    );
    expect(screen.getByRole("link", { name: /mytube/i })).toBeInTheDocument();
    expect(screen.getByRole("navigation", { name: /footer navigation/i })).toBeInTheDocument();
  });

  // ── page-wrap structure ───────────────────────────────────────────────────────

  it("renders a page-wrap div for non-auth routes", () => {
    mockPathname = "/";
    const { container } = render(
      <AppShell>
        <div>content</div>
      </AppShell>
    );
    const pageWrap = container.querySelector(".page-wrap");
    expect(pageWrap).toBeInTheDocument();
  });

  it("renders a shell div inside page-wrap for non-auth routes", () => {
    mockPathname = "/";
    const { container } = render(
      <AppShell>
        <div>content</div>
      </AppShell>
    );
    const shell = container.querySelector(".page-wrap .shell");
    expect(shell).toBeInTheDocument();
  });

  it("places SiteHeader inside the shell container", () => {
    mockPathname = "/";
    const { container } = render(
      <AppShell>
        <div>content</div>
      </AppShell>
    );
    const shell = container.querySelector(".shell");
    expect(shell).toContainElement(screen.getByRole("link", { name: /mytube/i }).closest("header"));
  });

  it("places children inside the shell container", () => {
    mockPathname = "/";
    const { container } = render(
      <AppShell>
        <div data-testid="page-content">content</div>
      </AppShell>
    );
    const shell = container.querySelector(".shell");
    expect(shell).toContainElement(screen.getByTestId("page-content"));
  });

  // ── Decorative elements ───────────────────────────────────────────────────────

  it("renders four decor elements for non-auth routes", () => {
    mockPathname = "/";
    const { container } = render(
      <AppShell>
        <div>content</div>
      </AppShell>
    );
    const decors = container.querySelectorAll(".decor");
    expect(decors).toHaveLength(4);
  });

  it("renders a .decor.play element", () => {
    mockPathname = "/";
    const { container } = render(
      <AppShell>
        <div>content</div>
      </AppShell>
    );
    expect(container.querySelector(".decor.play")).toBeInTheDocument();
  });

  it("renders a .decor.film element", () => {
    mockPathname = "/";
    const { container } = render(
      <AppShell>
        <div>content</div>
      </AppShell>
    );
    expect(container.querySelector(".decor.film")).toBeInTheDocument();
  });

  it("renders a .decor.camera element", () => {
    mockPathname = "/";
    const { container } = render(
      <AppShell>
        <div>content</div>
      </AppShell>
    );
    expect(container.querySelector(".decor.camera")).toBeInTheDocument();
  });

  it("renders a .decor.wave element", () => {
    mockPathname = "/";
    const { container } = render(
      <AppShell>
        <div>content</div>
      </AppShell>
    );
    expect(container.querySelector(".decor.wave")).toBeInTheDocument();
  });

  it("positions decor elements outside (as siblings of) the shell", () => {
    mockPathname = "/";
    const { container } = render(
      <AppShell>
        <div>content</div>
      </AppShell>
    );
    const shell = container.querySelector(".shell");
    const decorPlay = container.querySelector(".decor.play");
    // decor should NOT be inside shell
    expect(shell).not.toContainElement(decorPlay as HTMLElement);
  });

  // ── Auth routes — no shell ────────────────────────────────────────────────────

  it("does NOT render SiteHeader on /login", () => {
    mockPathname = "/login";
    render(
      <AppShell>
        <div>Login page</div>
      </AppShell>
    );
    expect(screen.queryByRole("link", { name: /mytube/i })).not.toBeInTheDocument();
  });

  it("does NOT render SiteFooter on /login", () => {
    mockPathname = "/login";
    render(
      <AppShell>
        <div>Login page</div>
      </AppShell>
    );
    expect(screen.queryByRole("navigation", { name: /footer navigation/i })).not.toBeInTheDocument();
  });

  it("still renders children on /login", () => {
    mockPathname = "/login";
    render(
      <AppShell>
        <div>Login page</div>
      </AppShell>
    );
    expect(screen.getByText("Login page")).toBeInTheDocument();
  });

  it("does NOT render the page-wrap on /login", () => {
    mockPathname = "/login";
    const { container } = render(
      <AppShell>
        <div>Login page</div>
      </AppShell>
    );
    expect(container.querySelector(".page-wrap")).not.toBeInTheDocument();
  });

  it("does NOT render decor elements on /login", () => {
    mockPathname = "/login";
    const { container } = render(
      <AppShell>
        <div>Login page</div>
      </AppShell>
    );
    expect(container.querySelectorAll(".decor")).toHaveLength(0);
  });

  it("does NOT render SiteHeader on /register", () => {
    mockPathname = "/register";
    render(
      <AppShell>
        <div>Register page</div>
      </AppShell>
    );
    expect(screen.queryByRole("link", { name: /mytube/i })).not.toBeInTheDocument();
  });

  it("does NOT render SiteFooter on /register", () => {
    mockPathname = "/register";
    render(
      <AppShell>
        <div>Register page</div>
      </AppShell>
    );
    expect(screen.queryByRole("navigation", { name: /footer navigation/i })).not.toBeInTheDocument();
  });

  it("still renders children on /register", () => {
    mockPathname = "/register";
    render(
      <AppShell>
        <div>Register page</div>
      </AppShell>
    );
    expect(screen.getByText("Register page")).toBeInTheDocument();
  });

  it("does NOT render decor elements on /register", () => {
    mockPathname = "/register";
    const { container } = render(
      <AppShell>
        <div>Register page</div>
      </AppShell>
    );
    expect(container.querySelectorAll(".decor")).toHaveLength(0);
  });
});
