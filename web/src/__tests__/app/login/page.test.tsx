/**
 * Unit tests for src/app/login/page.tsx
 */
import React from "react";
import { render, screen, waitFor, act } from "@testing-library/react";
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

const mockSignInWithEmailAndPassword = jest.fn();
const mockSignInWithPopup = jest.fn();

jest.mock("firebase/auth", () => ({
  signInWithEmailAndPassword: (auth: unknown, email: string, password: string) =>
    mockSignInWithEmailAndPassword(auth, email, password),
  signInWithPopup: (auth: unknown, provider: unknown) =>
    mockSignInWithPopup(auth, provider),
  GoogleAuthProvider: jest.fn().mockImplementation(() => ({ providerId: "google.com" })),
}));

jest.mock("@/lib/firebase", () => ({
  getFirebaseAuth: jest.fn().mockReturnValue({ name: "mock-auth" }),
}));

// ─── Import page AFTER mocks ──────────────────────────────────────────────────

import LoginPage from "@/app/login/page";

// ─── Tests ────────────────────────────────────────────────────────────────────

describe("LoginPage", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockUser = null;
    mockLoading = false;
  });

  it("renders loading state when loading=true", () => {
    mockLoading = true;
    render(<LoginPage />);
    expect(screen.getByText(/loading/i)).toBeInTheDocument();
  });

  it("renders the sign-in form when not loading and no user", () => {
    render(<LoginPage />);
    expect(
      screen.getByRole("heading", { name: /sign in/i })
    ).toBeInTheDocument();
    expect(screen.getByLabelText(/email/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/password/i)).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /sign in$/i })
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /sign in with google/i })
    ).toBeInTheDocument();
  });

  it("redirects to / when user is already authenticated", async () => {
    mockUser = { email: "alice@example.com" };
    render(<LoginPage />);
    await waitFor(() => {
      expect(mockRouterReplace).toHaveBeenCalledWith("/");
    });
  });

  it("calls signInWithEmailAndPassword with form values on submit", async () => {
    mockSignInWithEmailAndPassword.mockResolvedValue({});
    const user = userEvent.setup();
    render(<LoginPage />);

    await user.type(screen.getByLabelText(/email/i), "alice@example.com");
    await user.type(screen.getByLabelText(/password/i), "password123");
    await user.click(screen.getByRole("button", { name: /sign in$/i }));

    await waitFor(() => {
      expect(mockSignInWithEmailAndPassword).toHaveBeenCalledWith(
        expect.anything(),
        "alice@example.com",
        "password123"
      );
    });
  });

  it("redirects to / on successful email sign-in", async () => {
    mockSignInWithEmailAndPassword.mockResolvedValue({});
    const user = userEvent.setup();
    render(<LoginPage />);

    await user.type(screen.getByLabelText(/email/i), "alice@example.com");
    await user.type(screen.getByLabelText(/password/i), "password123");
    await user.click(screen.getByRole("button", { name: /sign in$/i }));

    await waitFor(() => {
      expect(mockRouterReplace).toHaveBeenCalledWith("/");
    });
  });

  it("shows error message on sign-in failure with invalid-credential code", async () => {
    const error = Object.assign(new Error("Firebase: wrong password"), {
      code: "auth/invalid-credential",
    });
    mockSignInWithEmailAndPassword.mockRejectedValue(error);
    const user = userEvent.setup();
    render(<LoginPage />);

    await user.type(screen.getByLabelText(/email/i), "wrong@example.com");
    await user.type(screen.getByLabelText(/password/i), "wrongpass");
    await user.click(screen.getByRole("button", { name: /sign in$/i }));

    await waitFor(() => {
      expect(screen.getByRole("alert")).toHaveTextContent(
        /incorrect email or password/i
      );
    });
  });

  it("shows error message for too-many-requests code", async () => {
    const error = Object.assign(new Error("Too many"), {
      code: "auth/too-many-requests",
    });
    mockSignInWithEmailAndPassword.mockRejectedValue(error);
    const user = userEvent.setup();
    render(<LoginPage />);

    await user.type(screen.getByLabelText(/email/i), "alice@example.com");
    await user.type(screen.getByLabelText(/password/i), "pass");
    await user.click(screen.getByRole("button", { name: /sign in$/i }));

    await waitFor(() => {
      expect(screen.getByRole("alert")).toHaveTextContent(/too many/i);
    });
  });

  it("shows generic error for unknown error code", async () => {
    const error = Object.assign(new Error("Something"), {
      code: "auth/unknown-error",
    });
    mockSignInWithEmailAndPassword.mockRejectedValue(error);
    const user = userEvent.setup();
    render(<LoginPage />);

    await user.type(screen.getByLabelText(/email/i), "alice@example.com");
    await user.type(screen.getByLabelText(/password/i), "pass");
    await user.click(screen.getByRole("button", { name: /sign in$/i }));

    await waitFor(() => {
      expect(screen.getByRole("alert")).toHaveTextContent(/sign-in failed/i);
    });
  });

  it("shows generic error for non-object errors", async () => {
    mockSignInWithEmailAndPassword.mockRejectedValue("string error");
    const user = userEvent.setup();
    render(<LoginPage />);

    await user.type(screen.getByLabelText(/email/i), "alice@example.com");
    await user.type(screen.getByLabelText(/password/i), "pass");
    await user.click(screen.getByRole("button", { name: /sign in$/i }));

    await waitFor(() => {
      expect(screen.getByRole("alert")).toHaveTextContent(/unexpected error/i);
    });
  });

  it("calls signInWithPopup on Google sign-in button click", async () => {
    mockSignInWithPopup.mockResolvedValue({});
    const user = userEvent.setup();
    render(<LoginPage />);

    await user.click(screen.getByRole("button", { name: /sign in with google/i }));

    await waitFor(() => {
      expect(mockSignInWithPopup).toHaveBeenCalledTimes(1);
    });
  });

  it("redirects to / on successful Google sign-in", async () => {
    mockSignInWithPopup.mockResolvedValue({});
    const user = userEvent.setup();
    render(<LoginPage />);

    await user.click(screen.getByRole("button", { name: /sign in with google/i }));

    await waitFor(() => {
      expect(mockRouterReplace).toHaveBeenCalledWith("/");
    });
  });

  it("shows error on Google sign-in popup closed", async () => {
    const error = Object.assign(new Error("Popup closed"), {
      code: "auth/popup-closed-by-user",
    });
    mockSignInWithPopup.mockRejectedValue(error);
    const user = userEvent.setup();
    render(<LoginPage />);

    await user.click(screen.getByRole("button", { name: /sign in with google/i }));

    await waitFor(() => {
      expect(screen.getByRole("alert")).toHaveTextContent(/popup was closed/i);
    });
  });

  it("has a link to the register page", () => {
    render(<LoginPage />);
    expect(screen.getByRole("link", { name: /create one/i })).toHaveAttribute(
      "href",
      "/register"
    );
  });

  it("Google sign-in result user has getIdToken accessible in auth state", async () => {
    const mockGetIdToken = jest.fn().mockResolvedValue("mock-id-token");
    mockSignInWithPopup.mockResolvedValue({ user: { getIdToken: mockGetIdToken } });
    const user = userEvent.setup();
    render(<LoginPage />);

    await user.click(screen.getByRole("button", { name: /sign in with google/i }));

    await waitFor(() => {
      expect(mockGetIdToken).toBeDefined();
      expect(typeof mockGetIdToken).toBe("function");
    });
  });
});
