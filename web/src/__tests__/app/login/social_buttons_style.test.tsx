/**
 * MYTUBE-459: Social login buttons — style and icons match redesign
 *
 * Verifies that the Google and GitHub .auth-btn buttons rendered by LoginPage
 * have the correct inline styles (border, borderRadius, background), the
 * w-full class, and the expected SVG icon children.
 */
import React from "react";
import { render, screen } from "@testing-library/react";

// ─── Mock next/navigation ─────────────────────────────────────────────────────

jest.mock("next/navigation", () => ({
  useRouter: () => ({ replace: jest.fn() }),
  useSearchParams: () => ({ get: () => null }),
}));

// ─── Mock AuthContext ─────────────────────────────────────────────────────────

jest.mock("@/context/AuthContext", () => ({
  useAuth: () => ({ user: null, loading: false }),
}));

// ─── Mock Firebase ────────────────────────────────────────────────────────────

jest.mock("firebase/auth", () => ({
  signInWithEmailAndPassword: jest.fn(),
  signInWithPopup: jest.fn(),
  GoogleAuthProvider: jest.fn().mockImplementation(() => ({ providerId: "google.com" })),
}));

jest.mock("@/lib/firebase", () => ({
  getFirebaseAuth: jest.fn().mockReturnValue({ name: "mock-auth" }),
}));

// ─── Import page AFTER mocks ──────────────────────────────────────────────────

import LoginPage from "@/app/login/page";

// ─── Helpers ──────────────────────────────────────────────────────────────────

function getAuthButtons() {
  const buttons = document.querySelectorAll("button.auth-btn");
  expect(buttons).toHaveLength(2);
  const googleBtn = buttons[0] as HTMLButtonElement;
  const githubBtn = buttons[1] as HTMLButtonElement;
  return { googleBtn, githubBtn };
}

// ─── Test suite ───────────────────────────────────────────────────────────────

describe("Social login buttons style and icons", () => {
  beforeEach(() => {
    render(<LoginPage />);
  });

  it("renders both .auth-btn buttons", () => {
    const buttons = document.querySelectorAll("button.auth-btn");
    expect(buttons).toHaveLength(2);
  });

  // ─── Google button ──────────────────────────────────────────────────────────

  it("Google button has border", () => {
    const { googleBtn } = getAuthButtons();
    expect(googleBtn.style.border).toBe("1.5px solid var(--border-light)");
  });

  it("Google button has borderRadius", () => {
    const { googleBtn } = getAuthButtons();
    expect(googleBtn.style.borderRadius).toBe("12px");
  });

  it("Google button has background", () => {
    const { googleBtn } = getAuthButtons();
    expect(googleBtn.style.background).toBe("var(--bg-content)");
  });

  it("Google button is full-width", () => {
    const { googleBtn } = getAuthButtons();
    expect(googleBtn.classList.contains("w-full")).toBe(true);
  });

  it("Google button contains a colored SVG icon", () => {
    const { googleBtn } = getAuthButtons();
    const svg = googleBtn.querySelector("svg");
    expect(svg).not.toBeNull();
    // The Google icon has 4 brand-color paths
    const paths = svg!.querySelectorAll("path[fill]");
    expect(paths.length).toBe(4);
    const fills = Array.from(paths).map((p) => p.getAttribute("fill"));
    expect(fills).toContain("#4285F4");
    expect(fills).toContain("#34A853");
    expect(fills).toContain("#FBBC05");
    expect(fills).toContain("#EA4335");
  });

  // ─── GitHub button ──────────────────────────────────────────────────────────

  it("GitHub button has border", () => {
    const { githubBtn } = getAuthButtons();
    expect(githubBtn.style.border).toBe("1.5px solid var(--border-light)");
  });

  it("GitHub button has borderRadius", () => {
    const { githubBtn } = getAuthButtons();
    expect(githubBtn.style.borderRadius).toBe("12px");
  });

  it("GitHub button has background", () => {
    const { githubBtn } = getAuthButtons();
    expect(githubBtn.style.background).toBe("var(--bg-content)");
  });

  it("GitHub button is full-width", () => {
    const { githubBtn } = getAuthButtons();
    expect(githubBtn.classList.contains("w-full")).toBe(true);
  });

  it("GitHub button contains an SVG icon", () => {
    const { githubBtn } = getAuthButtons();
    const svg = githubBtn.querySelector("svg");
    expect(svg).not.toBeNull();
    // The GitHub mark icon uses fill="currentColor" with a single path
    const paths = svg!.querySelectorAll("path");
    expect(paths.length).toBeGreaterThanOrEqual(1);
  });
});
