/**
 * MYTUBE-110: Access protected /settings page while unauthenticated — user redirected to login.
 *
 * Objective:
 *   Ensure that the /settings page is inaccessible to unauthenticated users and
 *   that the application automatically redirects them to /login via the shared
 *   React AuthContext.
 *
 * Preconditions:
 *   - The user is not logged in (no token in localStorage or context).
 *   - loading is false (auth state has been resolved).
 *
 * Steps:
 *   1. Render SettingsPage with user=null and loading=false (unauthenticated state).
 *
 * Expected Result:
 *   The application detects the unauthenticated state via the shared React
 *   Context/Store and automatically calls router.replace("/login").
 */

import React from "react";
import { render, waitFor } from "@testing-library/react";

// ─── Mock next/navigation ─────────────────────────────────────────────────────

const mockRouterReplace = jest.fn();
jest.mock("next/navigation", () => ({
  useRouter: () => ({ replace: mockRouterReplace }),
  usePathname: () => "/settings",
  useSearchParams: () => ({ toString: () => "" }),
}));

// ─── Mock AuthContext ─────────────────────────────────────────────────────────

let mockUser: { email: string } | null = null;
let mockLoading = false;
const mockGetIdToken = jest.fn().mockResolvedValue(null);
const mockSignOut = jest.fn().mockResolvedValue(undefined);

jest.mock("@/context/AuthContext", () => ({
  useAuth: () => ({
    user: mockUser,
    loading: mockLoading,
    getIdToken: mockGetIdToken,
    signOut: mockSignOut,
  }),
}));

// ─── Mock fetch (profile fetch is not expected for unauthenticated user) ──────

global.fetch = jest.fn();

// ─── Import page AFTER mocks ──────────────────────────────────────────────────

import SettingsPage from "@/app/settings/page";

// ─── Tests ────────────────────────────────────────────────────────────────────

describe("MYTUBE-110 — /settings redirect for unauthenticated user", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    // Precondition: user is NOT logged in, auth state has fully resolved
    mockUser = null;
    mockLoading = false;
  });

  it("redirects unauthenticated user from /settings to /login", async () => {
    // Step 1: Attempt to navigate directly to /settings by rendering the page
    // in an unauthenticated state (user=null, loading=false).
    render(<SettingsPage />);

    // Expected Result: router.replace("/login") is called, proving the
    // application detects the unauthenticated state via React Context and
    // redirects the user to the login page.
    await waitFor(() => {
      expect(mockRouterReplace).toHaveBeenCalledWith("/login?next=%2Fsettings");
    });
  });

  it("does not redirect while auth state is still loading", () => {
    // Guard: when loading=true the component must not redirect prematurely —
    // it should wait for the auth state to resolve before deciding.
    mockLoading = true;
    render(<SettingsPage />);

    // router.replace must NOT have been called during the loading phase.
    expect(mockRouterReplace).not.toHaveBeenCalled();
  });

  it("does not redirect an authenticated user away from /settings", async () => {
    // Counter-test: an authenticated user must stay on /settings (no redirect).
    mockUser = { email: "alice@example.com" };
    mockGetIdToken.mockResolvedValue("mock-token");
    (global.fetch as jest.Mock).mockResolvedValue({
      ok: true,
      json: async () => ({ username: "alice", avatar_url: null }),
    });

    render(<SettingsPage />);

    // Allow any async effects to settle.
    await waitFor(() => {
      expect(mockRouterReplace).not.toHaveBeenCalledWith("/login?next=%2Fsettings");
    });
  });
});
