/**
 * Unit tests for src/app/my-videos/page.tsx
 *
 * Key assertion: unauthenticated users are redirected to /login?next=%2Fmy-videos.
 */
import React from "react";
import { render, waitFor } from "@testing-library/react";

// ─── Mock next/navigation ─────────────────────────────────────────────────────

const mockRouterReplace = jest.fn();
const mockPathname = "/my-videos";

jest.mock("next/navigation", () => ({
  useRouter: () => ({ replace: mockRouterReplace }),
  useSearchParams: () => ({ get: jest.fn().mockReturnValue(null), toString: () => "" }),
  usePathname: () => mockPathname,
}));

// ─── Mock AuthContext ─────────────────────────────────────────────────────────

let mockUser: { email: string } | null = null;
let mockLoading = false;

jest.mock("@/context/AuthContext", () => ({
  useAuth: () => ({ user: mockUser, loading: mockLoading, getIdToken: jest.fn() }),
}));

// ─── Mock dashboard dependencies to avoid API calls ──────────────────────────

jest.mock("@/data/dashboardRepository", () => ({
  ApiDashboardVideoRepository: jest.fn().mockImplementation(() => ({
    listMyVideos: jest.fn().mockResolvedValue([]),
  })),
  ApiVideoManagementRepository: jest.fn().mockImplementation(() => ({
    updateVideo: jest.fn(),
    deleteVideo: jest.fn(),
  })),
}));

jest.mock("@/data/playlistRepository", () => ({
  ApiPlaylistRepository: jest.fn().mockImplementation(() => ({
    listMine: jest.fn().mockResolvedValue([]),
    create: jest.fn(),
    updateTitle: jest.fn(),
    deletePlaylist: jest.fn(),
    addVideo: jest.fn(),
    removeVideo: jest.fn(),
    getByID: jest.fn(),
    listByUsername: jest.fn(),
  })),
}));

// ─── Import page AFTER mocks ──────────────────────────────────────────────────

import MyVideosPage from "@/app/my-videos/page";

// ─── Tests ────────────────────────────────────────────────────────────────────

beforeEach(() => {
  jest.clearAllMocks();
  mockUser = null;
  mockLoading = false;
});

describe("MyVideosPage — unauthenticated redirect", () => {
  it("redirects unauthenticated users to /login?next=%2Fmy-videos", async () => {
    mockUser = null;
    mockLoading = false;

    render(<MyVideosPage />);

    await waitFor(() => {
      expect(mockRouterReplace).toHaveBeenCalledWith(
        "/login?next=%2Fmy-videos"
      );
    });
  });

  it("renders nothing (no flash) while redirect is in-flight for unauthenticated users", () => {
    mockUser = null;
    mockLoading = false;

    const { container } = render(<MyVideosPage />);

    // RequireAuth returns null when unauthenticated; container should be empty
    expect(container.firstChild).toBeNull();
  });

  it("shows loading spinner while auth state is resolving", () => {
    mockUser = null;
    mockLoading = true;

    const { getByText } = render(<MyVideosPage />);

    expect(getByText("Loading…")).toBeTruthy();
    expect(mockRouterReplace).not.toHaveBeenCalled();
  });

  it("renders content for authenticated users without redirecting", async () => {
    mockUser = { email: "user@example.com" };
    mockLoading = false;

    const { container } = render(<MyVideosPage />);

    await waitFor(() => {
      expect(container.firstChild).not.toBeNull();
    });
    expect(mockRouterReplace).not.toHaveBeenCalled();
  });
});
