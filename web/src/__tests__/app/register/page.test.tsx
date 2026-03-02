/**
 * Unit tests for src/app/register/page.tsx
 */
import React from "react";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

// ─── Mock next/navigation ─────────────────────────────────────────────────────

const mockRouterReplace = jest.fn();
jest.mock("next/navigation", () => ({
  useRouter: () => ({ replace: mockRouterReplace }),
}));

// ─── Mock AuthContext ─────────────────────────────────────────────────────────

let mockUser: { email: string } | null = null;
let mockLoading = false;

jest.mock("@/context/AuthContext", () => ({
  useAuth: () => ({ user: mockUser, loading: mockLoading }),
}));

// ─── Mock Firebase ────────────────────────────────────────────────────────────

const mockGetIdToken = jest.fn().mockResolvedValue("mock-id-token");
const mockCreateUserWithEmailAndPassword = jest.fn();

jest.mock("firebase/auth", () => ({
  createUserWithEmailAndPassword: (auth: unknown, email: string, password: string) =>
    mockCreateUserWithEmailAndPassword(auth, email, password),
}));

jest.mock("@/lib/firebase", () => ({
  getFirebaseAuth: jest.fn().mockReturnValue({ name: "mock-auth" }),
}));

// ─── Mock fetch ───────────────────────────────────────────────────────────────

const mockFetch = jest.fn();
global.fetch = mockFetch;

// ─── Import page AFTER mocks ──────────────────────────────────────────────────

import RegisterPage from "@/app/register/page";

// ─── Tests ────────────────────────────────────────────────────────────────────

describe("RegisterPage", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockUser = null;
    mockLoading = false;
    mockFetch.mockResolvedValue({ ok: true });
    mockGetIdToken.mockResolvedValue("mock-id-token");
  });

  it("renders loading state when loading=true", () => {
    mockLoading = true;
    render(<RegisterPage />);
    expect(screen.getByText(/loading/i)).toBeInTheDocument();
  });

  it("renders the registration form when not loading and no user", () => {
    render(<RegisterPage />);
    expect(
      screen.getByRole("heading", { name: /create an account/i })
    ).toBeInTheDocument();
    expect(screen.getByLabelText(/email/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/password/i)).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /create account/i })
    ).toBeInTheDocument();
  });

  it("redirects to / when user is already authenticated", async () => {
    mockUser = { email: "alice@example.com" };
    render(<RegisterPage />);
    await waitFor(() => {
      expect(mockRouterReplace).toHaveBeenCalledWith("/");
    });
  });

  it("calls createUserWithEmailAndPassword on form submit", async () => {
    mockCreateUserWithEmailAndPassword.mockResolvedValue({
      user: { getIdToken: mockGetIdToken },
    });
    const user = userEvent.setup();
    render(<RegisterPage />);

    await user.type(screen.getByLabelText(/email/i), "alice@example.com");
    await user.type(screen.getByLabelText(/password/i), "password123");
    await user.click(screen.getByRole("button", { name: /create account/i }));

    await waitFor(() => {
      expect(mockCreateUserWithEmailAndPassword).toHaveBeenCalledWith(
        expect.anything(),
        "alice@example.com",
        "password123"
      );
    });
  });

  it("calls GET /api/me with Bearer token after creating account", async () => {
    mockCreateUserWithEmailAndPassword.mockResolvedValue({
      user: { getIdToken: mockGetIdToken },
    });
    const user = userEvent.setup();
    render(<RegisterPage />);

    await user.type(screen.getByLabelText(/email/i), "alice@example.com");
    await user.type(screen.getByLabelText(/password/i), "password123");
    await user.click(screen.getByRole("button", { name: /create account/i }));

    await waitFor(() => {
      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining("/api/me"),
        expect.objectContaining({
          method: "GET",
          headers: expect.objectContaining({
            Authorization: "Bearer mock-id-token",
          }),
        })
      );
    });
  });

  it("redirects to / after successful registration", async () => {
    mockCreateUserWithEmailAndPassword.mockResolvedValue({
      user: { getIdToken: mockGetIdToken },
    });
    const user = userEvent.setup();
    render(<RegisterPage />);

    await user.type(screen.getByLabelText(/email/i), "alice@example.com");
    await user.type(screen.getByLabelText(/password/i), "password123");
    await user.click(screen.getByRole("button", { name: /create account/i }));

    await waitFor(() => {
      expect(mockRouterReplace).toHaveBeenCalledWith("/");
    });
  });

  it("shows error when email is already in use", async () => {
    const error = Object.assign(new Error("Email in use"), {
      code: "auth/email-already-in-use",
    });
    mockCreateUserWithEmailAndPassword.mockRejectedValue(error);
    const user = userEvent.setup();
    render(<RegisterPage />);

    await user.type(screen.getByLabelText(/email/i), "existing@example.com");
    await user.type(screen.getByLabelText(/password/i), "password123");
    await user.click(screen.getByRole("button", { name: /create account/i }));

    await waitFor(() => {
      expect(screen.getByRole("alert")).toHaveTextContent(/already exists/i);
    });
  });

  it("shows error for weak password", async () => {
    const error = Object.assign(new Error("Weak password"), {
      code: "auth/weak-password",
    });
    mockCreateUserWithEmailAndPassword.mockRejectedValue(error);
    const user = userEvent.setup();
    render(<RegisterPage />);

    await user.type(screen.getByLabelText(/email/i), "alice@example.com");
    await user.type(screen.getByLabelText(/password/i), "abc");
    await user.click(screen.getByRole("button", { name: /create account/i }));

    await waitFor(() => {
      expect(screen.getByRole("alert")).toHaveTextContent(/at least 6 characters/i);
    });
  });

  it("shows error for invalid email reported by Firebase", async () => {
    // Use a structurally valid email so HTML5 form validation passes, but
    // have Firebase reject it with auth/invalid-email.
    const error = Object.assign(new Error("Invalid email"), {
      code: "auth/invalid-email",
    });
    mockCreateUserWithEmailAndPassword.mockRejectedValue(error);
    const user = userEvent.setup();
    render(<RegisterPage />);

    await user.type(screen.getByLabelText(/email/i), "bad@domain");
    await user.type(screen.getByLabelText(/password/i), "password123");
    await user.click(screen.getByRole("button", { name: /create account/i }));

    await waitFor(() => {
      expect(screen.getByRole("alert")).toHaveTextContent(/invalid email/i);
    });
  });

  it("shows generic error for unknown Firebase error code", async () => {
    const error = Object.assign(new Error("Unknown"), {
      code: "auth/some-unknown-code",
    });
    mockCreateUserWithEmailAndPassword.mockRejectedValue(error);
    const user = userEvent.setup();
    render(<RegisterPage />);

    await user.type(screen.getByLabelText(/email/i), "alice@example.com");
    await user.type(screen.getByLabelText(/password/i), "password123");
    await user.click(screen.getByRole("button", { name: /create account/i }));

    await waitFor(() => {
      expect(screen.getByRole("alert")).toHaveTextContent(
        /registration failed/i
      );
    });
  });

  it("has a link to the login page", () => {
    render(<RegisterPage />);
    expect(screen.getByRole("link", { name: /sign in/i })).toHaveAttribute(
      "href",
      "/login"
    );
  });
});
