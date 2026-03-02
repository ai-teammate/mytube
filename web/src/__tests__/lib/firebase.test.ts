/**
 * Unit tests for src/lib/firebase.ts
 *
 * Firebase SDK functions are mocked to avoid real network/SDK initialisation
 * in the test environment.
 */
import { resetAuthInstance } from "@/lib/firebase";

// ─── Mock Firebase App ────────────────────────────────────────────────────────

const mockGetApp = jest.fn();
const mockInitializeApp = jest.fn().mockReturnValue({ name: "mock-app" });
const mockGetApps = jest.fn().mockReturnValue([]);

jest.mock("firebase/app", () => ({
  getApp: () => mockGetApp(),
  initializeApp: (config: unknown) => mockInitializeApp(config),
  getApps: () => mockGetApps(),
}));

// ─── Mock Firebase Auth ───────────────────────────────────────────────────────

const mockGetAuth = jest.fn().mockReturnValue({ name: "mock-auth" });
const mockConnectAuthEmulator = jest.fn();
const mockSetPersistence = jest.fn().mockResolvedValue(undefined);

jest.mock("firebase/auth", () => ({
  getAuth: (app: unknown) => mockGetAuth(app),
  connectAuthEmulator: (auth: unknown, url: string, opts: unknown) =>
    mockConnectAuthEmulator(auth, url, opts),
  browserLocalPersistence: "LOCAL",
  setPersistence: (auth: unknown, persistence: unknown) =>
    mockSetPersistence(auth, persistence),
}));

// ─── Tests ────────────────────────────────────────────────────────────────────

describe("getFirebaseAuth", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    resetAuthInstance();
    // Default: no apps initialised yet.
    mockGetApps.mockReturnValue([]);
    mockInitializeApp.mockReturnValue({ name: "mock-app" });
    mockGetAuth.mockReturnValue({ name: "mock-auth" });
    mockSetPersistence.mockResolvedValue(undefined);
    delete process.env.NEXT_PUBLIC_USE_FIREBASE_EMULATOR;
  });

  it("calls initializeApp when no apps are registered", async () => {
    const { getFirebaseAuth } = await import("@/lib/firebase");
    getFirebaseAuth();
    expect(mockInitializeApp).toHaveBeenCalledTimes(1);
  });

  it("calls getApp instead of initializeApp when apps already exist", async () => {
    mockGetApps.mockReturnValue([{ name: "existing" }]);
    mockGetApp.mockReturnValue({ name: "existing" });

    const { getFirebaseAuth } = await import("@/lib/firebase");
    getFirebaseAuth();

    expect(mockInitializeApp).not.toHaveBeenCalled();
    expect(mockGetApp).toHaveBeenCalled();
  });

  it("returns the auth instance from getAuth", async () => {
    const mockAuth = { name: "my-auth-instance" };
    mockGetAuth.mockReturnValue(mockAuth);

    const { getFirebaseAuth } = await import("@/lib/firebase");
    const result = getFirebaseAuth();

    expect(result).toBe(mockAuth);
  });

  it("caches the auth instance (getAuth called only once on repeated calls)", async () => {
    const { getFirebaseAuth } = await import("@/lib/firebase");
    getFirebaseAuth();
    getFirebaseAuth();
    getFirebaseAuth();

    expect(mockGetAuth).toHaveBeenCalledTimes(1);
  });

  it("does NOT connect emulator when NEXT_PUBLIC_USE_FIREBASE_EMULATOR is not set", async () => {
    const { getFirebaseAuth } = await import("@/lib/firebase");
    getFirebaseAuth();
    expect(mockConnectAuthEmulator).not.toHaveBeenCalled();
  });

  it("does NOT connect emulator when NEXT_PUBLIC_USE_FIREBASE_EMULATOR is 'false'", async () => {
    process.env.NEXT_PUBLIC_USE_FIREBASE_EMULATOR = "false";
    const { getFirebaseAuth } = await import("@/lib/firebase");
    getFirebaseAuth();
    expect(mockConnectAuthEmulator).not.toHaveBeenCalled();
  });

  it("connects emulator when NEXT_PUBLIC_USE_FIREBASE_EMULATOR is 'true'", async () => {
    process.env.NEXT_PUBLIC_USE_FIREBASE_EMULATOR = "true";
    // jsdom environment has window defined, so the emulator branch should run.
    const { getFirebaseAuth } = await import("@/lib/firebase");
    getFirebaseAuth();
    expect(mockConnectAuthEmulator).toHaveBeenCalledWith(
      expect.anything(),
      "http://localhost:9099",
      { disableWarnings: true }
    );
  });
});

describe("resetAuthInstance", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    resetAuthInstance();
    mockGetApps.mockReturnValue([]);
    mockGetAuth.mockReturnValue({ name: "mock-auth" });
    mockSetPersistence.mockResolvedValue(undefined);
  });

  it("forces getAuth to be called again after reset", async () => {
    const { getFirebaseAuth } = await import("@/lib/firebase");
    getFirebaseAuth();
    expect(mockGetAuth).toHaveBeenCalledTimes(1);

    resetAuthInstance();
    getFirebaseAuth();
    expect(mockGetAuth).toHaveBeenCalledTimes(2);
  });
});
