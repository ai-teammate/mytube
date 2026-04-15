/**
 * Unit tests for src/app/settings/page.tsx
 */
import React from "react";
import { render, screen, waitFor, act } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

// ─── Mock next/navigation ─────────────────────────────────────────────────────

const mockRouterReplace = jest.fn();
jest.mock("next/navigation", () => ({
  useRouter: () => ({ replace: mockRouterReplace }),
  usePathname: () => "/settings",
  useSearchParams: () => null,
}));

// ─── Mock AuthContext ─────────────────────────────────────────────────────────

let mockUser: { email: string } | null = null;
let mockLoading = false;
const mockGetIdToken = jest.fn().mockResolvedValue("mock-token");
const mockSignOut = jest.fn().mockResolvedValue(undefined);

jest.mock("@/context/AuthContext", () => ({
  useAuth: () => ({
    user: mockUser,
    loading: mockLoading,
    getIdToken: mockGetIdToken,
    signOut: mockSignOut,
  }),
}));

// ─── Mock fetch ───────────────────────────────────────────────────────────────

const mockFetch = jest.fn();
global.fetch = mockFetch;

// ─── Import page AFTER mocks ──────────────────────────────────────────────────

import SettingsPage from "@/app/settings/page";

// ─── Tests ────────────────────────────────────────────────────────────────────

describe("SettingsPage", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockUser = { email: "alice@example.com" };
    mockLoading = false;
    mockGetIdToken.mockResolvedValue("mock-token");
    mockSignOut.mockResolvedValue(undefined);
    // Default GET /api/me response.
    mockFetch.mockResolvedValue({
      ok: true,
      json: async () => ({ username: "alice", avatar_url: null }),
    });
  });

  it("renders loading state when loading=true", () => {
    mockLoading = true;
    mockUser = null;
    render(<SettingsPage />);
    expect(screen.getByText(/loading/i)).toBeInTheDocument();
  });

  it("redirects to /login?next=/settings when user is null and not loading", async () => {
    mockUser = null;
    mockLoading = false;
    render(<SettingsPage />);
    await waitFor(() => {
      expect(mockRouterReplace).toHaveBeenCalledWith("/login?next=%2Fsettings");
    });
  });

  it("renders the settings form for authenticated user", async () => {
    render(<SettingsPage />);
    await waitFor(() => {
      expect(
        screen.getByRole("heading", { name: /account settings/i })
      ).toBeInTheDocument();
    });
    expect(screen.getByLabelText(/username/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/avatar url/i)).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /save settings/i })
    ).toBeInTheDocument();
  });

  it("displays user email in the header", async () => {
    render(<SettingsPage />);
    await waitFor(() => {
      expect(screen.getByText("alice@example.com")).toBeInTheDocument();
    });
  });

  it("pre-fills the form with data from GET /api/me", async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      json: async () => ({
        username: "prefilled-alice",
        avatar_url: "https://example.com/avatar.png",
      }),
    });

    render(<SettingsPage />);
    await waitFor(() => {
      expect(screen.getByDisplayValue("prefilled-alice")).toBeInTheDocument();
    });
    expect(
      screen.getByDisplayValue("https://example.com/avatar.png")
    ).toBeInTheDocument();
  });

  it("calls PUT /api/me with correct payload on form submit", async () => {
    mockFetch
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ username: "alice", avatar_url: null }),
      })
      .mockResolvedValueOnce({ ok: true, json: async () => ({}) });

    const user = userEvent.setup();
    render(<SettingsPage />);

    await waitFor(() =>
      expect(screen.getByLabelText(/username/i)).toBeInTheDocument()
    );

    // Clear and type new username.
    await user.clear(screen.getByLabelText(/username/i));
    await user.type(screen.getByLabelText(/username/i), "newalice");
    await user.type(
      screen.getByLabelText(/avatar url/i),
      "https://example.com/new.png"
    );
    await user.click(screen.getByRole("button", { name: /save settings/i }));

    await waitFor(() => {
      const putCall = mockFetch.mock.calls.find(
        (call) => call[1]?.method === "PUT"
      );
      expect(putCall).toBeDefined();
      expect(putCall?.[0]).toContain("/api/me");
      expect(putCall?.[1]?.headers?.Authorization).toBe("Bearer mock-token");
    });
  });

  it("shows success message after successful PUT", async () => {
    mockFetch
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ username: "alice", avatar_url: null }),
      })
      .mockResolvedValueOnce({ ok: true, json: async () => ({}) });

    const user = userEvent.setup();
    render(<SettingsPage />);

    await waitFor(() =>
      expect(screen.getByLabelText(/username/i)).toBeInTheDocument()
    );

    await user.click(screen.getByRole("button", { name: /save settings/i }));

    await waitFor(() => {
      expect(screen.getByRole("status")).toHaveTextContent(
        /settings saved successfully/i
      );
    });
  });

  it("shows error when PUT /api/me returns non-ok response", async () => {
    mockFetch
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ username: "alice", avatar_url: null }),
      })
      .mockResolvedValueOnce({
        ok: false,
        json: async () => ({ error: "username too long" }),
      });

    const user = userEvent.setup();
    render(<SettingsPage />);

    await waitFor(() =>
      expect(screen.getByLabelText(/username/i)).toBeInTheDocument()
    );
    await user.click(screen.getByRole("button", { name: /save settings/i }));

    await waitFor(() => {
      expect(screen.getByRole("alert")).toHaveTextContent(/username too long/i);
    });
  });

  it("shows fallback error when PUT response body has no error field", async () => {
    mockFetch
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ username: "alice", avatar_url: null }),
      })
      .mockResolvedValueOnce({
        ok: false,
        json: async () => ({}),
      });

    const user = userEvent.setup();
    render(<SettingsPage />);

    await waitFor(() =>
      expect(screen.getByLabelText(/username/i)).toBeInTheDocument()
    );
    await user.click(screen.getByRole("button", { name: /save settings/i }));

    await waitFor(() => {
      expect(screen.getByRole("alert")).toHaveTextContent(
        /failed to save settings/i
      );
    });
  });

  it("shows network error message on fetch failure", async () => {
    mockFetch
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ username: "alice", avatar_url: null }),
      })
      .mockRejectedValueOnce(new Error("Network error"));

    const user = userEvent.setup();
    render(<SettingsPage />);

    await waitFor(() =>
      expect(screen.getByLabelText(/username/i)).toBeInTheDocument()
    );
    await user.click(screen.getByRole("button", { name: /save settings/i }));

    await waitFor(() => {
      expect(screen.getByRole("alert")).toHaveTextContent(/network error/i);
    });
  });

  it("shows auth error when getIdToken returns null on save", async () => {
    // First call (fetchProfile): return null so no fetch occurs.
    // Second call (handleSave): also return null → trigger auth error.
    mockGetIdToken.mockResolvedValue(null);

    const user = userEvent.setup();
    render(<SettingsPage />);

    // Form renders with empty username; we must fill it to pass HTML validation.
    await waitFor(() =>
      expect(screen.getByLabelText(/username/i)).toBeInTheDocument()
    );
    await user.type(screen.getByLabelText(/username/i), "alice");

    await user.click(screen.getByRole("button", { name: /save settings/i }));

    await waitFor(() => {
      expect(screen.getByRole("alert")).toHaveTextContent(
        /not authenticated/i
      );
    });
  });

  it("calls signOut and redirects to /login on sign-out click", async () => {
    const user = userEvent.setup();
    render(<SettingsPage />);

    await waitFor(() =>
      expect(screen.getByRole("button", { name: /sign out/i })).toBeInTheDocument()
    );
    await user.click(screen.getByRole("button", { name: /sign out/i }));

    expect(mockSignOut).toHaveBeenCalledTimes(1);
    await waitFor(() => {
      expect(mockRouterReplace).toHaveBeenCalledWith("/login");
    });
  });

  it("does not call fetch for profile if getIdToken returns null", async () => {
    mockGetIdToken.mockResolvedValue(null);
    render(<SettingsPage />);

    await waitFor(() =>
      expect(screen.getByLabelText(/username/i)).toBeInTheDocument()
    );

    // fetch should not have been called for profile data since token is null.
    expect(mockFetch).not.toHaveBeenCalled();
  });

  // ─── Avatar preview tests ───────────────────────────────────────────────────

  it("does not render avatar preview when avatarUrl is empty", async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      json: async () => ({ username: "alice", avatar_url: null }),
    });

    render(<SettingsPage />);
    await waitFor(() =>
      expect(screen.getByLabelText(/username/i)).toBeInTheDocument()
    );

    expect(screen.queryByLabelText("Avatar preview")).toBeNull();
  });

  it("renders avatar preview when avatarUrl is pre-filled from profile", async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      json: async () => ({
        username: "alice",
        avatar_url: "https://example.com/avatar.png",
      }),
    });

    render(<SettingsPage />);
    await waitFor(() =>
      expect(screen.getByLabelText("Avatar preview")).toBeInTheDocument()
    );

    const preview = screen.getByRole("img", { name: /avatar preview/i });
    expect(preview.querySelector("img")).toHaveAttribute(
      "src",
      "https://example.com/avatar.png"
    );
  });

  it("renders avatar preview reactively as user types a URL", async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      json: async () => ({ username: "alice", avatar_url: null }),
    });

    const user = userEvent.setup();
    render(<SettingsPage />);

    await waitFor(() =>
      expect(screen.getByLabelText(/avatar url/i)).toBeInTheDocument()
    );

    // No preview before typing.
    expect(screen.queryByLabelText("Avatar preview")).toBeNull();

    await user.type(
      screen.getByLabelText(/avatar url/i),
      "https://example.com/new.png"
    );

    await waitFor(() =>
      expect(screen.getByLabelText("Avatar preview")).toBeInTheDocument()
    );
    const preview = screen.getByRole("img", { name: /avatar preview/i });
    expect(preview.querySelector("img")).toHaveAttribute(
      "src",
      "https://example.com/new.png"
    );
  });
});
