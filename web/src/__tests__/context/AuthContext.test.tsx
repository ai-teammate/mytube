/**
 * Unit tests for src/context/AuthContext.tsx
 */
import React from "react";
import { render, screen, waitFor, act } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { AuthProvider, useAuth, HEARTBEAT_INTERVAL_MS, HEARTBEAT_PROBE_TIMEOUT_MS } from "@/context/AuthContext";

// ─── Mock Firebase ────────────────────────────────────────────────────────────

let onAuthStateChangedCallback: ((user: unknown) => void) | null = null;
let onAuthStateChangedErrorCallback: ((error: Error) => void) | null = null;

const mockSignOut = jest.fn().mockResolvedValue(undefined);
const mockGetAuth = jest.fn().mockReturnValue({ name: "mock-auth" });
const mockOnAuthStateChanged = jest
  .fn()
  .mockImplementation((_auth, cb, errorCb?: (error: Error) => void) => {
    onAuthStateChangedCallback = cb;
    onAuthStateChangedErrorCallback = errorCb ?? null;
    return () => {}; // unsubscribe
  });

jest.mock("firebase/auth", () => ({
  onAuthStateChanged: (
    auth: unknown,
    cb: (user: unknown) => void,
    errorCb?: (error: Error) => void
  ) => mockOnAuthStateChanged(auth, cb, errorCb),
  signOut: (auth: unknown) => mockSignOut(auth),
  browserLocalPersistence: "LOCAL",
  setPersistence: jest.fn().mockResolvedValue(undefined),
  getAuth: () => mockGetAuth(),
}));

jest.mock("@/lib/firebase", () => ({
  getFirebaseAuth: () => mockGetAuth(),
  resetAuthInstance: jest.fn(),
}));

// ─── Test helpers ─────────────────────────────────────────────────────────────

/** Consumer component that exposes auth state via data-testid attributes */
function AuthConsumer() {
  const { user, loading, authError, getIdToken, signOut } = useAuth();
  return (
    <div>
      <span data-testid="loading">{String(loading)}</span>
      <span data-testid="auth-error">{String(authError)}</span>
      <span data-testid="user-email">{user?.email ?? "null"}</span>
      <button
        data-testid="sign-out-btn"
        onClick={() => signOut()}
      >
        Sign out
      </button>
      <button
        data-testid="get-token-btn"
        onClick={async () => {
          const token = await getIdToken();
          document.getElementById("token-result")!.textContent = token ?? "null";
        }}
      >
        Get token
      </button>
      <span id="token-result" />
    </div>
  );
}

function renderWithProvider() {
  return render(
    <AuthProvider>
      <AuthConsumer />
    </AuthProvider>
  );
}

// ─── Tests ────────────────────────────────────────────────────────────────────

describe("AuthProvider", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    onAuthStateChangedCallback = null;
    onAuthStateChangedErrorCallback = null;
    mockSignOut.mockResolvedValue(undefined);
  });

  it("starts in loading=true state before auth resolves", () => {
    renderWithProvider();
    expect(screen.getByTestId("loading")).toHaveTextContent("true");
  });

  it("sets loading=false after onAuthStateChanged fires with null", async () => {
    renderWithProvider();
    act(() => {
      onAuthStateChangedCallback?.(null);
    });
    await waitFor(() =>
      expect(screen.getByTestId("loading")).toHaveTextContent("false")
    );
  });

  it("sets loading=false when Firebase fires the auth error callback (e.g., auth/invalid-api-key)", async () => {
    renderWithProvider();
    expect(screen.getByTestId("loading")).toHaveTextContent("true");

    act(() => {
      onAuthStateChangedErrorCallback?.(
        Object.assign(new Error("Firebase: Error (auth/invalid-api-key)."), {
          code: "auth/invalid-api-key",
        })
      );
    });

    await waitFor(() =>
      expect(screen.getByTestId("loading")).toHaveTextContent("false")
    );
  });

  it("sets authError=true when Firebase fires the auth error callback", async () => {
    renderWithProvider();

    act(() => {
      onAuthStateChangedErrorCallback?.(
        Object.assign(new Error("Firebase: Error (auth/invalid-api-key)."), {
          code: "auth/invalid-api-key",
        })
      );
    });

    await waitFor(() =>
      expect(screen.getByTestId("auth-error")).toHaveTextContent("true")
    );
  });

  it("keeps authError=false on successful auth state change", async () => {
    renderWithProvider();

    act(() => {
      onAuthStateChangedCallback?.(null);
    });

    await waitFor(() =>
      expect(screen.getByTestId("loading")).toHaveTextContent("false")
    );
    expect(screen.getByTestId("auth-error")).toHaveTextContent("false");
  });

  it("sets user.email when onAuthStateChanged fires with a user", async () => {
    renderWithProvider();
    act(() => {
      onAuthStateChangedCallback?.({ email: "alice@example.com", getIdToken: jest.fn() });
    });
    await waitFor(() =>
      expect(screen.getByTestId("user-email")).toHaveTextContent(
        "alice@example.com"
      )
    );
  });

  it("sets user to null when onAuthStateChanged fires with null", async () => {
    renderWithProvider();
    act(() => {
      onAuthStateChangedCallback?.(null);
    });
    await waitFor(() =>
      expect(screen.getByTestId("user-email")).toHaveTextContent("null")
    );
  });

  it("calls firebaseSignOut and sets user to null on signOut()", async () => {
    const user = userEvent.setup();
    renderWithProvider();

    act(() => {
      onAuthStateChangedCallback?.({ email: "alice@example.com", getIdToken: jest.fn() });
    });
    await waitFor(() =>
      expect(screen.getByTestId("user-email")).toHaveTextContent("alice@example.com")
    );

    await user.click(screen.getByTestId("sign-out-btn"));

    expect(mockSignOut).toHaveBeenCalledTimes(1);
    await waitFor(() =>
      expect(screen.getByTestId("user-email")).toHaveTextContent("null")
    );
  });

  it("getIdToken returns null when user is null", async () => {
    const user = userEvent.setup();
    renderWithProvider();

    act(() => {
      onAuthStateChangedCallback?.(null);
    });
    await waitFor(() =>
      expect(screen.getByTestId("loading")).toHaveTextContent("false")
    );

    await user.click(screen.getByTestId("get-token-btn"));

    await waitFor(() =>
      expect(document.getElementById("token-result")).toHaveTextContent("null")
    );
  });

  it("getIdToken returns token string when user is set", async () => {
    const userEvent_ = userEvent.setup();
    const mockGetIdToken = jest.fn().mockResolvedValue("id-token-value");
    renderWithProvider();

    act(() => {
      onAuthStateChangedCallback?.({
        email: "alice@example.com",
        getIdToken: mockGetIdToken,
      });
    });
    await waitFor(() =>
      expect(screen.getByTestId("loading")).toHaveTextContent("false")
    );

    await userEvent_.click(screen.getByTestId("get-token-btn"));

    await waitFor(() =>
      expect(document.getElementById("token-result")).toHaveTextContent(
        "id-token-value"
      )
    );
  });

  it("getIdToken returns null when getIdToken throws", async () => {
    const userEvent_ = userEvent.setup();
    const mockGetIdTokenFails = jest
      .fn()
      .mockRejectedValue(new Error("token error"));
    renderWithProvider();

    act(() => {
      onAuthStateChangedCallback?.({
        email: "alice@example.com",
        getIdToken: mockGetIdTokenFails,
      });
    });
    await waitFor(() =>
      expect(screen.getByTestId("loading")).toHaveTextContent("false")
    );

    await userEvent_.click(screen.getByTestId("get-token-btn"));

    await waitFor(() =>
      expect(document.getElementById("token-result")).toHaveTextContent("null")
    );
  });
});

describe("useAuth outside AuthProvider", () => {
  it("throws an error when used outside AuthProvider", () => {
    const spy = jest.spyOn(console, "error").mockImplementation(() => {});
    expect(() => {
      render(<AuthConsumer />);
    }).toThrow("useAuth must be used within an AuthProvider");
    spy.mockRestore();
  });
});

describe("AuthProvider — Firebase initialisation failure", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    onAuthStateChangedCallback = null;
  });

  it("renders children with user=null and loading=false when getFirebaseAuth throws auth/invalid-api-key", async () => {
    // Simulate the deployed-site scenario: Firebase SDK throws because
    // NEXT_PUBLIC_FIREBASE_API_KEY was absent at build time.
    mockGetAuth.mockImplementationOnce(() => {
      throw new Error("Firebase: Error (auth/invalid-api-key).");
    });

    // Suppress React's error-boundary console noise for this expected failure.
    const consoleSpy = jest.spyOn(console, "error").mockImplementation(() => {});

    renderWithProvider();

    // After the fix: children must render in an unauthenticated but non-crashed state.
    await waitFor(() =>
      expect(screen.getByTestId("loading")).toHaveTextContent("false")
    );
    expect(screen.getByTestId("user-email")).toHaveTextContent("null");

    consoleSpy.mockRestore();
  });

  it("sets authError=true when getFirebaseAuth throws", async () => {
    mockGetAuth.mockImplementationOnce(() => {
      throw new Error("Firebase: Error (auth/invalid-api-key).");
    });

    const consoleSpy = jest.spyOn(console, "error").mockImplementation(() => {});

    renderWithProvider();

    await waitFor(() =>
      expect(screen.getByTestId("auth-error")).toHaveTextContent("true")
    );

    consoleSpy.mockRestore();
  });
});

// ─── Heartbeat / mid-session reachability tests (MYTUBE-381) ──────────────────

describe("AuthProvider — mid-session reachability heartbeat", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    jest.useFakeTimers();
    onAuthStateChangedCallback = null;
    onAuthStateChangedErrorCallback = null;
  });

  afterEach(() => {
    jest.useRealTimers();
  });

  it("sets authError=true after HEARTBEAT_INTERVAL_MS when getIdToken(true) throws mid-session", async () => {
    const mockGetIdToken = jest
      .fn()
      .mockRejectedValue(new Error("auth/network-request-failed"));

    renderWithProvider();

    // Simulate successful login
    act(() => {
      onAuthStateChangedCallback?.({
        email: "alice@example.com",
        getIdToken: mockGetIdToken,
      });
    });

    await waitFor(() =>
      expect(screen.getByTestId("loading")).toHaveTextContent("false")
    );
    expect(screen.getByTestId("auth-error")).toHaveTextContent("false");

    // Advance time to trigger the heartbeat probe
    await act(async () => {
      jest.advanceTimersByTime(HEARTBEAT_INTERVAL_MS);
      // Allow the async probe to settle
      await Promise.resolve();
    });

    await waitFor(() =>
      expect(screen.getByTestId("auth-error")).toHaveTextContent("true")
    );
  });

  it("does not set authError when getIdToken(true) succeeds", async () => {
    const mockGetIdToken = jest.fn().mockResolvedValue("fresh-token");

    renderWithProvider();

    act(() => {
      onAuthStateChangedCallback?.({
        email: "alice@example.com",
        getIdToken: mockGetIdToken,
      });
    });

    await waitFor(() =>
      expect(screen.getByTestId("loading")).toHaveTextContent("false")
    );

    await act(async () => {
      jest.advanceTimersByTime(HEARTBEAT_INTERVAL_MS);
      await Promise.resolve();
    });

    expect(screen.getByTestId("auth-error")).toHaveTextContent("false");
  });

  it("calls getIdToken with forceRefresh=true during heartbeat", async () => {
    const mockGetIdToken = jest.fn().mockResolvedValue("fresh-token");

    renderWithProvider();

    act(() => {
      onAuthStateChangedCallback?.({
        email: "alice@example.com",
        getIdToken: mockGetIdToken,
      });
    });

    await waitFor(() =>
      expect(screen.getByTestId("loading")).toHaveTextContent("false")
    );

    await act(async () => {
      jest.advanceTimersByTime(HEARTBEAT_INTERVAL_MS);
      await Promise.resolve();
    });

    expect(mockGetIdToken).toHaveBeenCalledWith(true);
  });

  it("does not start heartbeat when user is null (unauthenticated)", async () => {
    const mockGetIdToken = jest.fn().mockResolvedValue("fresh-token");

    renderWithProvider();

    act(() => {
      onAuthStateChangedCallback?.(null);
    });

    await waitFor(() =>
      expect(screen.getByTestId("loading")).toHaveTextContent("false")
    );

    await act(async () => {
      jest.advanceTimersByTime(HEARTBEAT_INTERVAL_MS * 3);
      await Promise.resolve();
    });

    expect(mockGetIdToken).not.toHaveBeenCalled();
    expect(screen.getByTestId("auth-error")).toHaveTextContent("false");
  });

  it("stops heartbeat after authError is set (does not call getIdToken again)", async () => {
    let callCount = 0;
    const mockGetIdToken = jest.fn().mockImplementation(() => {
      callCount++;
      return Promise.reject(new Error("network-failure"));
    });

    renderWithProvider();

    act(() => {
      onAuthStateChangedCallback?.({
        email: "alice@example.com",
        getIdToken: mockGetIdToken,
      });
    });

    await waitFor(() =>
      expect(screen.getByTestId("loading")).toHaveTextContent("false")
    );

    // First interval fires — triggers failure and sets authError
    await act(async () => {
      jest.advanceTimersByTime(HEARTBEAT_INTERVAL_MS);
      await Promise.resolve();
    });

    await waitFor(() =>
      expect(screen.getByTestId("auth-error")).toHaveTextContent("true")
    );

    const countAfterFirstError = callCount;

    // Advance more — heartbeat should have stopped
    await act(async () => {
      jest.advanceTimersByTime(HEARTBEAT_INTERVAL_MS * 3);
      await Promise.resolve();
    });

    expect(callCount).toBe(countAfterFirstError);
  });

  it("sets authError=true when heartbeat probe exceeds HEARTBEAT_PROBE_TIMEOUT_MS (degraded network simulation)", async () => {
    // getIdToken returns a promise that never resolves, simulating a hanging
    // network request on a degraded-but-reachable connection.
    const mockGetIdToken = jest.fn().mockReturnValue(new Promise(() => {}));

    renderWithProvider();

    act(() => {
      onAuthStateChangedCallback?.({
        email: "alice@example.com",
        getIdToken: mockGetIdToken,
      });
    });

    await waitFor(() =>
      expect(screen.getByTestId("loading")).toHaveTextContent("false")
    );

    expect(screen.getByTestId("auth-error")).toHaveTextContent("false");

    // Advance past the interval so the probe fires, then past the probe timeout
    // so the internal timeout promise rejects.
    await act(async () => {
      jest.advanceTimersByTime(HEARTBEAT_INTERVAL_MS + HEARTBEAT_PROBE_TIMEOUT_MS);
      await Promise.resolve();
    });

    await waitFor(() =>
      expect(screen.getByTestId("auth-error")).toHaveTextContent("true")
    );
  });
});
