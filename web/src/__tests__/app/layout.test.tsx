/**
 * Unit tests for src/app/layout.tsx (RootLayout)
 */
import React from "react";
import { render, screen } from "@testing-library/react";

// ─── Mock next/font/google ────────────────────────────────────────────────────
jest.mock("next/font/google", () => ({
  Inter: () => ({
    className: "mock-inter-class",
    variable: "--font-inter",
    style: { fontFamily: "Inter" },
  }),
}));

// ─── Mock next/navigation ─────────────────────────────────────────────────────
jest.mock("next/navigation", () => ({
  usePathname: () => "/",
  useRouter: () => ({ push: jest.fn() }),
}));

// ─── Mock AuthContext ─────────────────────────────────────────────────────────
jest.mock("@/context/AuthContext", () => ({
  AuthProvider: ({ children }: { children: React.ReactNode }) => (
    <div data-testid="auth-provider">{children}</div>
  ),
  useAuth: () => ({ user: null, loading: false, signOut: jest.fn() }),
}));

// ─── Mock AppShell ────────────────────────────────────────────────────────────
jest.mock("@/components/AppShell", () => ({
  __esModule: true,
  default: ({ children }: { children: React.ReactNode }) => (
    <div data-testid="app-shell">{children}</div>
  ),
}));

// ─── Mock globals.css ────────────────────────────────────────────────────────
jest.mock("../../../app/globals.css", () => ({}), { virtual: true });

// ─── Import after mocks ───────────────────────────────────────────────────────
import RootLayout, { metadata } from "@/app/layout";

// ─── Tests ────────────────────────────────────────────────────────────────────

describe("RootLayout", () => {
  it("renders children inside the layout", () => {
    render(
      <RootLayout>
        <div data-testid="child-content">Hello World</div>
      </RootLayout>
    );
    expect(screen.getByTestId("child-content")).toBeInTheDocument();
    expect(screen.getByText("Hello World")).toBeInTheDocument();
  });

  it("wraps children in AuthProvider", () => {
    render(
      <RootLayout>
        <span>content</span>
      </RootLayout>
    );
    expect(screen.getByTestId("auth-provider")).toBeInTheDocument();
  });

  it("wraps children in AppShell", () => {
    render(
      <RootLayout>
        <span>content</span>
      </RootLayout>
    );
    expect(screen.getByTestId("app-shell")).toBeInTheDocument();
  });

  it("applies Inter font variable class to the body", () => {
    render(
      <RootLayout>
        <span>content</span>
      </RootLayout>
    );
    const body = document.querySelector("body");
    expect(body?.className).toContain("--font-inter");
  });

  it("applies antialiased class to the body", () => {
    render(
      <RootLayout>
        <span>content</span>
      </RootLayout>
    );
    const body = document.querySelector("body");
    expect(body?.className).toContain("antialiased");
  });

  it("does NOT include Geist font variables in body className", () => {
    render(
      <RootLayout>
        <span>content</span>
      </RootLayout>
    );
    const body = document.querySelector("body");
    expect(body?.className).not.toContain("geist");
    expect(body?.className).not.toContain("--font-geist");
  });
});

describe("metadata export", () => {
  it("has the correct title", () => {
    expect(metadata.title).toBe("mytube");
  });

  it("has the correct description", () => {
    expect(metadata.description).toBe("Personal video platform");
  });
});
