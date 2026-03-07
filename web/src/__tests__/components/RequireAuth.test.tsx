/**
 * Unit tests for src/components/RequireAuth.tsx
 */
import React from "react";
import { render, screen, waitFor } from "@testing-library/react";

// ─── Mock next/navigation ─────────────────────────────────────────────────────

const mockRouterReplace = jest.fn();
let mockPathname = "/protected";
let mockSearchParams: URLSearchParams | null = null;

jest.mock("next/navigation", () => ({
  useRouter: () => ({ replace: mockRouterReplace }),
  usePathname: () => mockPathname,
  useSearchParams: () => mockSearchParams,
}));

// ─── Mock AuthContext ─────────────────────────────────────────────────────────

let mockUser: { email: string } | null = null;
let mockLoading = false;

jest.mock("@/context/AuthContext", () => ({
  useAuth: () => ({ user: mockUser, loading: mockLoading }),
}));

// ─── Import component AFTER mocks ─────────────────────────────────────────────

import RequireAuth from "@/components/RequireAuth";

// ─── Helpers ──────────────────────────────────────────────────────────────────

function renderWithChild(pathname = "/protected", searchParams: URLSearchParams | null = null) {
  mockPathname = pathname;
  mockSearchParams = searchParams;
  return render(
    <RequireAuth>
      <div data-testid="protected-content">Protected content</div>
    </RequireAuth>
  );
}

// ─── Tests ────────────────────────────────────────────────────────────────────

describe("RequireAuth", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockUser = null;
    mockLoading = false;
    mockPathname = "/protected";
    mockSearchParams = null;
  });

  // ─── Loading state ──────────────────────────────────────────────────────────

  it("renders a loading spinner while auth state is resolving", () => {
    mockLoading = true;
    renderWithChild();
    expect(screen.getByText(/loading/i)).toBeInTheDocument();
  });

  it("does not render children while auth state is resolving", () => {
    mockLoading = true;
    renderWithChild();
    expect(screen.queryByTestId("protected-content")).not.toBeInTheDocument();
  });

  it("renders the spinner with a spin animation element", () => {
    mockLoading = true;
    renderWithChild();
    // The spinner div has aria-hidden="true"
    const spinners = document.querySelectorAll('[aria-hidden="true"]');
    expect(spinners.length).toBeGreaterThan(0);
  });

  // ─── Unauthenticated redirect ───────────────────────────────────────────────

  it("redirects to /login?next=<encoded_pathname> when not authenticated", async () => {
    mockPathname = "/upload";
    mockLoading = false;
    mockUser = null;
    renderWithChild("/upload");
    await waitFor(() => {
      expect(mockRouterReplace).toHaveBeenCalledWith("/login?next=%2Fupload");
    });
  });

  it("redirects to /login?next=%2Fdashboard for /dashboard", async () => {
    mockLoading = false;
    mockUser = null;
    renderWithChild("/dashboard");
    await waitFor(() => {
      expect(mockRouterReplace).toHaveBeenCalledWith("/login?next=%2Fdashboard");
    });
  });

  it("redirects to /login?next=%2Fsettings for /settings", async () => {
    mockLoading = false;
    mockUser = null;
    renderWithChild("/settings");
    await waitFor(() => {
      expect(mockRouterReplace).toHaveBeenCalledWith("/login?next=%2Fsettings");
    });
  });

  it("renders null (not children) while redirect is in-flight", async () => {
    mockUser = null;
    mockLoading = false;
    const { container } = renderWithChild();
    // Children should not be rendered
    expect(screen.queryByTestId("protected-content")).not.toBeInTheDocument();
    // Wait for redirect to fire
    await waitFor(() => expect(mockRouterReplace).toHaveBeenCalled());
  });

  it("does not redirect while still loading (user may be authenticated)", () => {
    mockLoading = true;
    mockUser = null;
    renderWithChild();
    expect(mockRouterReplace).not.toHaveBeenCalled();
  });

  // ─── Authenticated ──────────────────────────────────────────────────────────

  it("renders children when user is authenticated", () => {
    mockUser = { email: "alice@example.com" };
    mockLoading = false;
    renderWithChild();
    expect(screen.getByTestId("protected-content")).toBeInTheDocument();
  });

  it("does not redirect when user is authenticated", () => {
    mockUser = { email: "alice@example.com" };
    mockLoading = false;
    renderWithChild();
    expect(mockRouterReplace).not.toHaveBeenCalled();
  });

  it("does not show the loading spinner when authenticated", () => {
    mockUser = { email: "alice@example.com" };
    mockLoading = false;
    renderWithChild();
    expect(screen.queryByText(/loading/i)).not.toBeInTheDocument();
  });

  // ─── Auth state transitions ─────────────────────────────────────────────────

  it("redirects after loading completes with no user", async () => {
    // Start loading, then resolve without a user
    mockLoading = true;
    const { rerender } = renderWithChild("/upload");
    expect(mockRouterReplace).not.toHaveBeenCalled();

    // Simulate auth state resolved: no user
    mockLoading = false;
    rerender(
      <RequireAuth>
        <div data-testid="protected-content">Protected content</div>
      </RequireAuth>
    );

    await waitFor(() => {
      expect(mockRouterReplace).toHaveBeenCalledWith("/login?next=%2Fupload");
    });
  });

  it("shows children after loading completes with a user", async () => {
    // Start loading
    mockLoading = true;
    const { rerender } = renderWithChild();
    expect(screen.queryByTestId("protected-content")).not.toBeInTheDocument();

    // Simulate auth state resolved: user present
    mockLoading = false;
    mockUser = { email: "alice@example.com" };
    rerender(
      <RequireAuth>
        <div data-testid="protected-content">Protected content</div>
      </RequireAuth>
    );

    expect(screen.getByTestId("protected-content")).toBeInTheDocument();
  });

  // ─── Query parameter preservation ──────────────────────────────────────────

  it("preserves query parameters in the next redirect when unauthenticated", async () => {
    mockLoading = false;
    mockUser = null;
    const searchParams = new URLSearchParams("category=gaming&priority=high");
    renderWithChild("/upload", searchParams);
    await waitFor(() => {
      expect(mockRouterReplace).toHaveBeenCalledWith(
        "/login?next=%2Fupload%3Fcategory%3Dgaming%26priority%3Dhigh"
      );
    });
  });

  it("redirects to path-only next when there are no query parameters", async () => {
    mockLoading = false;
    mockUser = null;
    renderWithChild("/upload", null);
    await waitFor(() => {
      expect(mockRouterReplace).toHaveBeenCalledWith("/login?next=%2Fupload");
    });
  });

  it("preserves empty search params as path-only next", async () => {
    mockLoading = false;
    mockUser = null;
    renderWithChild("/upload", new URLSearchParams(""));
    await waitFor(() => {
      expect(mockRouterReplace).toHaveBeenCalledWith("/login?next=%2Fupload");
    });
  });
});
