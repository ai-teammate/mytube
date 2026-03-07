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
});
