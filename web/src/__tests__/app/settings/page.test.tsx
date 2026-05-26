/**
 * Unit tests for src/app/settings/page.tsx
 */
import React from "react";
import { render, screen, waitFor, act, fireEvent } from "@testing-library/react";
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
const mockSetAvatarUrl = jest.fn();

jest.mock("@/context/AuthContext", () => ({
  useAuth: () => ({
    user: mockUser,
    loading: mockLoading,
    getIdToken: mockGetIdToken,
    signOut: mockSignOut,
    avatarUrl: "",
    setAvatarUrl: mockSetAvatarUrl,
  }),
}));

// ─── Mock fetch ───────────────────────────────────────────────────────────────

const mockFetch = jest.fn();
global.fetch = mockFetch;

// ─── Import page AFTER mocks ──────────────────────────────────────────────────

import SettingsPage from "@/app/settings/page";

// ─── Helper ───────────────────────────────────────────────────────────────────

function makeFile(
  name: string,
  type: string,
  sizeBytes: number
): File {
  const blob = new Blob([new Uint8Array(sizeBytes)], { type });
  return new File([blob], name, { type });
}

// ─── Tests ────────────────────────────────────────────────────────────────────

describe("SettingsPage", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockUser = { email: "alice@example.com" };
    mockLoading = false;
    mockGetIdToken.mockResolvedValue("mock-token");
    mockSignOut.mockResolvedValue(undefined);
    mockSetAvatarUrl.mockReset();
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

  // ─── Avatar file upload tests ────────────────────────────────────────────────

  it("renders the file upload control and Upload button", async () => {
    render(<SettingsPage />);
    await waitFor(() =>
      expect(screen.getByLabelText(/upload avatar/i)).toBeInTheDocument()
    );
    expect(screen.getByRole("button", { name: /^upload$/i })).toBeInTheDocument();
  });

  it("Upload button is disabled when no file is selected", async () => {
    render(<SettingsPage />);
    await waitFor(() =>
      expect(screen.getByRole("button", { name: /^upload$/i })).toBeInTheDocument()
    );
    expect(screen.getByRole("button", { name: /^upload$/i })).toBeDisabled();
  });

  it("shows inline error and keeps Upload button disabled when file type is invalid", async () => {
    render(<SettingsPage />);
    await waitFor(() =>
      expect(screen.getByLabelText(/upload avatar/i)).toBeInTheDocument()
    );

    const file = makeFile("avatar.gif", "image/gif", 1024);
    const fileInput = screen.getByLabelText(/upload avatar/i) as HTMLInputElement;
    Object.defineProperty(fileInput, "files", { value: [file], configurable: true });
    fireEvent.change(fileInput);

    await waitFor(() =>
      expect(screen.getByRole("alert")).toHaveTextContent(/only jpeg and png/i)
    );
    expect(screen.getByRole("button", { name: /^upload$/i })).toBeDisabled();
  });

  it("shows inline error when file exceeds 5 MB", async () => {
    const user = userEvent.setup();
    render(<SettingsPage />);
    await waitFor(() =>
      expect(screen.getByLabelText(/upload avatar/i)).toBeInTheDocument()
    );

    const file = makeFile("big.jpg", "image/jpeg", 6 * 1024 * 1024);
    await user.upload(screen.getByLabelText(/upload avatar/i), file);

    await waitFor(() =>
      expect(screen.getByRole("alert")).toHaveTextContent(/too large/i)
    );
    expect(screen.getByRole("button", { name: /^upload$/i })).toBeDisabled();
  });

  it("enables Upload button when a valid file is selected", async () => {
    const user = userEvent.setup();
    render(<SettingsPage />);
    await waitFor(() =>
      expect(screen.getByLabelText(/upload avatar/i)).toBeInTheDocument()
    );

    const file = makeFile("avatar.png", "image/png", 1024);
    await user.upload(screen.getByLabelText(/upload avatar/i), file);

    await waitFor(() =>
      expect(screen.getByRole("button", { name: /^upload$/i })).not.toBeDisabled()
    );
  });

  it("calls POST /api/me/avatar with FormData and auth header on upload", async () => {
    mockFetch
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ username: "alice", avatar_url: null }),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ avatar_url: "https://cdn.example.com/alice.jpg" }),
      });

    const user = userEvent.setup();
    render(<SettingsPage />);
    await waitFor(() =>
      expect(screen.getByLabelText(/upload avatar/i)).toBeInTheDocument()
    );

    const file = makeFile("avatar.jpg", "image/jpeg", 1024);
    await user.upload(screen.getByLabelText(/upload avatar/i), file);
    await user.click(screen.getByRole("button", { name: /^upload$/i }));

    await waitFor(() => {
      const postCall = mockFetch.mock.calls.find(
        (call) => call[1]?.method === "POST"
      );
      expect(postCall).toBeDefined();
      expect(postCall?.[0]).toContain("/api/me/avatar");
      expect(postCall?.[1]?.headers?.Authorization).toBe("Bearer mock-token");
      expect(postCall?.[1]?.body).toBeInstanceOf(FormData);
    });
  });

  it('sends the avatar file under the field name "avatar" (not "file")', async () => {
    mockFetch
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ username: "alice", avatar_url: null }),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ avatar_url: "https://cdn.example.com/alice.jpg" }),
      });

    const user = userEvent.setup();
    render(<SettingsPage />);
    await waitFor(() =>
      expect(screen.getByLabelText(/upload avatar/i)).toBeInTheDocument()
    );

    const file = makeFile("avatar.jpg", "image/jpeg", 1024);
    await user.upload(screen.getByLabelText(/upload avatar/i), file);
    await user.click(screen.getByRole("button", { name: /^upload$/i }));

    await waitFor(() => {
      const postCall = mockFetch.mock.calls.find(
        (call) => call[1]?.method === "POST"
      );
      expect(postCall).toBeDefined();
      const body = postCall?.[1]?.body as FormData;
      expect(body).toBeInstanceOf(FormData);
      // The backend reads the field as "avatar" — the frontend must use the same name.
      expect(body.get("avatar")).not.toBeNull();
      expect(body.get("file")).toBeNull();
    });
  });

  it("populates avatarUrl and shows success message after successful upload", async () => {
    jest.useFakeTimers();
    mockFetch
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ username: "alice", avatar_url: null }),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ avatar_url: "https://cdn.example.com/alice.jpg" }),
      });

    const user = userEvent.setup({ advanceTimers: jest.advanceTimersByTime });
    render(<SettingsPage />);
    await waitFor(() =>
      expect(screen.getByLabelText(/upload avatar/i)).toBeInTheDocument()
    );

    const file = makeFile("avatar.jpg", "image/jpeg", 1024);
    await user.upload(screen.getByLabelText(/upload avatar/i), file);
    await user.click(screen.getByRole("button", { name: /^upload$/i }));

    await waitFor(() =>
      expect(screen.getByRole("status")).toHaveTextContent(/avatar uploaded successfully/i)
    );
    // avatarUrl should be updated → avatar preview should appear
    await waitFor(() =>
      expect(screen.getByDisplayValue("https://cdn.example.com/alice.jpg")).toBeInTheDocument()
    );
    // File input value should be cleared after successful upload.
    expect((screen.getByLabelText(/upload avatar/i) as HTMLInputElement).value).toBe("");

    // Success message auto-dismisses after 3 seconds.
    act(() => {
      jest.advanceTimersByTime(3000);
    });
    await waitFor(() =>
      expect(screen.queryByRole("status")).toBeNull()
    );

    jest.useRealTimers();
  });

  it("shows upload error when POST /api/me/avatar returns non-ok", async () => {
    mockFetch
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ username: "alice", avatar_url: null }),
      })
      .mockResolvedValueOnce({
        ok: false,
        json: async () => ({ error: "file too large" }),
      });

    const user = userEvent.setup();
    render(<SettingsPage />);
    await waitFor(() =>
      expect(screen.getByLabelText(/upload avatar/i)).toBeInTheDocument()
    );

    const file = makeFile("avatar.jpg", "image/jpeg", 1024);
    await user.upload(screen.getByLabelText(/upload avatar/i), file);
    await user.click(screen.getByRole("button", { name: /^upload$/i }));

    await waitFor(() =>
      expect(screen.getByRole("alert")).toHaveTextContent(/file too large/i)
    );
  });

  it("shows fallback upload error when POST response body has no error field", async () => {
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
      expect(screen.getByLabelText(/upload avatar/i)).toBeInTheDocument()
    );

    const file = makeFile("avatar.png", "image/png", 512);
    await user.upload(screen.getByLabelText(/upload avatar/i), file);
    await user.click(screen.getByRole("button", { name: /^upload$/i }));

    await waitFor(() =>
      expect(screen.getByRole("alert")).toHaveTextContent(/upload failed/i)
    );
  });

  it("shows upload network error on fetch rejection", async () => {
    mockFetch
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ username: "alice", avatar_url: null }),
      })
      .mockRejectedValueOnce(new Error("Network error"));

    const user = userEvent.setup();
    render(<SettingsPage />);
    await waitFor(() =>
      expect(screen.getByLabelText(/upload avatar/i)).toBeInTheDocument()
    );

    const file = makeFile("avatar.jpg", "image/jpeg", 1024);
    await user.upload(screen.getByLabelText(/upload avatar/i), file);
    await user.click(screen.getByRole("button", { name: /^upload$/i }));

    await waitFor(() =>
      expect(screen.getByRole("alert")).toHaveTextContent(/network error/i)
    );
  });

  it("shows upload auth error when getIdToken returns null during upload", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ username: "alice", avatar_url: null }),
    });
    // Second call (upload) → null token
    mockGetIdToken
      .mockResolvedValueOnce("mock-token") // fetchProfile
      .mockResolvedValueOnce(null);        // handleAvatarUpload

    const user = userEvent.setup();
    render(<SettingsPage />);
    await waitFor(() =>
      expect(screen.getByLabelText(/upload avatar/i)).toBeInTheDocument()
    );

    const file = makeFile("avatar.jpg", "image/jpeg", 1024);
    await user.upload(screen.getByLabelText(/upload avatar/i), file);
    await user.click(screen.getByRole("button", { name: /^upload$/i }));

    await waitFor(() =>
      expect(screen.getByRole("alert")).toHaveTextContent(/not authenticated/i)
    );
  });

  it("shows Uploading… text and disables Upload button while upload is in progress", async () => {
    let resolveUpload!: (value: unknown) => void;
    const uploadPromise = new Promise((res) => { resolveUpload = res; });

    mockFetch
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ username: "alice", avatar_url: null }),
      })
      .mockReturnValueOnce(uploadPromise);

    const user = userEvent.setup();
    render(<SettingsPage />);
    await waitFor(() =>
      expect(screen.getByLabelText(/upload avatar/i)).toBeInTheDocument()
    );

    const file = makeFile("avatar.png", "image/png", 1024);
    await user.upload(screen.getByLabelText(/upload avatar/i), file);
    await user.click(screen.getByRole("button", { name: /^upload$/i }));

    // While in-flight the button should show "Uploading…" and be disabled.
    await waitFor(() =>
      expect(screen.getByRole("button", { name: /uploading/i })).toBeDisabled()
    );

    // Resolve the upload to clean up.
    resolveUpload({ ok: true, json: async () => ({ avatar_url: "https://cdn.example.com/a.jpg" }) });
  });

  it("does not clear the existing Avatar URL field on upload error", async () => {
    mockFetch
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ username: "alice", avatar_url: "https://existing.com/avatar.png" }),
      })
      .mockResolvedValueOnce({
        ok: false,
        json: async () => ({ error: "server error" }),
      });

    const user = userEvent.setup();
    render(<SettingsPage />);
    await waitFor(() =>
      expect(screen.getByDisplayValue("https://existing.com/avatar.png")).toBeInTheDocument()
    );

    const file = makeFile("avatar.jpg", "image/jpeg", 1024);
    await user.upload(screen.getByLabelText(/upload avatar/i), file);
    await user.click(screen.getByRole("button", { name: /^upload$/i }));

    await waitFor(() =>
      expect(screen.getByRole("alert")).toHaveTextContent(/server error/i)
    );
    // Avatar URL field must still have the original value.
    expect(screen.getByDisplayValue("https://existing.com/avatar.png")).toBeInTheDocument();
  });

  // ─── Remove avatar tests ─────────────────────────────────────────────────────

  it("does not render Remove avatar button when avatarUrl is empty", async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      json: async () => ({ username: "alice", avatar_url: null }),
    });

    render(<SettingsPage />);
    await waitFor(() =>
      expect(screen.getByLabelText(/username/i)).toBeInTheDocument()
    );

    expect(screen.queryByRole("button", { name: /remove avatar/i })).toBeNull();
  });

  it("renders Remove avatar button when avatarUrl is non-empty", async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      json: async () => ({ username: "alice", avatar_url: "https://cdn.example.com/a.png" }),
    });

    render(<SettingsPage />);
    await waitFor(() =>
      expect(screen.getByRole("button", { name: /remove avatar/i })).toBeInTheDocument()
    );
  });

  it("calls DELETE /api/me/avatar with auth header on remove click", async () => {
    mockFetch
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ username: "alice", avatar_url: "https://cdn.example.com/a.png" }),
      })
      .mockResolvedValueOnce({ ok: true, json: async () => ({}) });

    const user = userEvent.setup();
    render(<SettingsPage />);
    await waitFor(() =>
      expect(screen.getByRole("button", { name: /remove avatar/i })).toBeInTheDocument()
    );

    await user.click(screen.getByRole("button", { name: /remove avatar/i }));

    await waitFor(() => {
      const deleteCall = mockFetch.mock.calls.find(
        (call) => call[1]?.method === "DELETE"
      );
      expect(deleteCall).toBeDefined();
      expect(deleteCall?.[0]).toContain("/api/me/avatar");
      expect(deleteCall?.[1]?.headers?.Authorization).toBe("Bearer mock-token");
    });
  });

  it("clears avatarUrl and calls setAvatarUrl after successful remove", async () => {
    mockFetch
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ username: "alice", avatar_url: "https://cdn.example.com/a.png" }),
      })
      .mockResolvedValueOnce({ ok: true, json: async () => ({}) });

    const user = userEvent.setup();
    render(<SettingsPage />);
    await waitFor(() =>
      expect(screen.getByRole("button", { name: /remove avatar/i })).toBeInTheDocument()
    );

    await user.click(screen.getByRole("button", { name: /remove avatar/i }));

    await waitFor(() => {
      // Remove avatar button should disappear (avatarUrl cleared).
      expect(screen.queryByRole("button", { name: /remove avatar/i })).toBeNull();
    });

    expect(mockSetAvatarUrl).toHaveBeenCalledWith("");
  });

  it("shows inline error when DELETE /api/me/avatar returns non-ok", async () => {
    mockFetch
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ username: "alice", avatar_url: "https://cdn.example.com/a.png" }),
      })
      .mockResolvedValueOnce({
        ok: false,
        json: async () => ({ error: "remove failed" }),
      });

    const user = userEvent.setup();
    render(<SettingsPage />);
    await waitFor(() =>
      expect(screen.getByRole("button", { name: /remove avatar/i })).toBeInTheDocument()
    );

    await user.click(screen.getByRole("button", { name: /remove avatar/i }));

    await waitFor(() => {
      expect(screen.getByRole("alert")).toHaveTextContent(/remove failed/i);
    });
  });

  it("shows fallback remove error when response body has no error field", async () => {
    mockFetch
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ username: "alice", avatar_url: "https://cdn.example.com/a.png" }),
      })
      .mockResolvedValueOnce({ ok: false, json: async () => ({}) });

    const user = userEvent.setup();
    render(<SettingsPage />);
    await waitFor(() =>
      expect(screen.getByRole("button", { name: /remove avatar/i })).toBeInTheDocument()
    );

    await user.click(screen.getByRole("button", { name: /remove avatar/i }));

    await waitFor(() => {
      expect(screen.getByRole("alert")).toHaveTextContent(/failed to remove avatar/i);
    });
  });

  it("shows network error on remove fetch rejection", async () => {
    mockFetch
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ username: "alice", avatar_url: "https://cdn.example.com/a.png" }),
      })
      .mockRejectedValueOnce(new Error("Network error"));

    const user = userEvent.setup();
    render(<SettingsPage />);
    await waitFor(() =>
      expect(screen.getByRole("button", { name: /remove avatar/i })).toBeInTheDocument()
    );

    await user.click(screen.getByRole("button", { name: /remove avatar/i }));

    await waitFor(() => {
      expect(screen.getByRole("alert")).toHaveTextContent(/network error/i);
    });
  });

  it("shows remove auth error when getIdToken returns null on remove", async () => {
    // First call (fetchProfile): returns token so profile loads with avatar.
    // Second call (handleAvatarRemove): returns null → auth error.
    mockGetIdToken
      .mockResolvedValueOnce("mock-token")
      .mockResolvedValue(null);

    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ username: "alice", avatar_url: "https://cdn.example.com/a.png" }),
    });

    const user = userEvent.setup();
    render(<SettingsPage />);
    await waitFor(() =>
      expect(screen.getByRole("button", { name: /remove avatar/i })).toBeInTheDocument()
    );

    await user.click(screen.getByRole("button", { name: /remove avatar/i }));

    await waitFor(() => {
      expect(screen.getByRole("alert")).toHaveTextContent(/not authenticated/i);
    });
  });
});
