/**
 * Unit tests for src/app/dashboard/page.tsx
 */
import React from "react";
import { render, screen, within, waitFor, act } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type {
  DashboardVideo,
  DashboardVideoRepository,
  UpdateVideoParams,
  UpdatedVideo,
  VideoManagementRepository,
} from "@/domain/dashboard";
import type { PlaylistRepository, PlaylistSummary } from "@/domain/playlist";

// ─── Mock next/navigation ─────────────────────────────────────────────────────

const mockRouterReplace = jest.fn();
let mockSearchParamsGet = jest.fn().mockReturnValue(null);

jest.mock("next/navigation", () => ({
  useRouter: () => ({ replace: mockRouterReplace }),
  useSearchParams: () => ({ get: mockSearchParamsGet }),
}));

// ─── Mock AuthContext ─────────────────────────────────────────────────────────

let mockUser: { email: string } | null = null;
let mockLoading = false;
const mockGetIdToken = jest.fn().mockResolvedValue("mock-token");

jest.mock("@/context/AuthContext", () => ({
  useAuth: () => ({
    user: mockUser,
    loading: mockLoading,
    getIdToken: mockGetIdToken,
  }),
}));

// ─── Mock repository modules ──────────────────────────────────────────────────
// Prevent real API calls during tests.

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

import { DashboardContent as DashboardPage } from "@/app/dashboard/_content";

// ─── Helpers ──────────────────────────────────────────────────────────────────

function makeDashboardVideo(
  overrides: Partial<DashboardVideo> = {}
): DashboardVideo {
  return {
    id: "vid-1",
    title: "Test Video",
    status: "ready",
    thumbnailUrl: "https://cdn.example.com/thumb.jpg",
    viewCount: 42,
    createdAt: "2024-01-15T10:00:00Z",
    description: null,
    categoryId: null,
    tags: [],
    ...overrides,
  };
}

function makeDashboardRepo(
  impl: (token: string) => Promise<DashboardVideo[]>
): DashboardVideoRepository {
  return { listMyVideos: impl };
}

function makeManagementRepo(overrides?: Partial<VideoManagementRepository>): VideoManagementRepository {
  return {
    updateVideo: jest.fn().mockResolvedValue({
      id: "vid-1",
      title: "Updated",
      description: null,
      status: "ready",
      thumbnailUrl: null,
      viewCount: 10,
      tags: [],
      uploader: { username: "alice", avatarUrl: null },
    } as UpdatedVideo),
    deleteVideo: jest.fn().mockResolvedValue(undefined),
    ...overrides,
  };
}

function makePlaylist(overrides: Partial<PlaylistSummary> = {}): PlaylistSummary {
  return {
    id: "pl-1",
    title: "My Playlist",
    ownerUsername: "alice",
    createdAt: "2024-01-01T00:00:00Z",
    ...overrides,
  };
}

function makePlaylistRepo(
  overrides: Partial<PlaylistRepository> = {}
): PlaylistRepository {
  return {
    listMine: jest.fn().mockResolvedValue([]),
    create: jest.fn().mockResolvedValue(makePlaylist()),
    updateTitle: jest.fn().mockResolvedValue(makePlaylist({ title: "Renamed" })),
    deletePlaylist: jest.fn().mockResolvedValue(undefined),
    addVideo: jest.fn(),
    removeVideo: jest.fn(),
    getByID: jest.fn(),
    listByUsername: jest.fn(),
    ...overrides,
  };
}

function renderDashboard(
  dashboardRepo?: DashboardVideoRepository,
  managementRepo?: VideoManagementRepository,
  playlistRepo?: PlaylistRepository
) {
  return render(
    <DashboardPage
      dashboardRepo={dashboardRepo ?? makeDashboardRepo(() => Promise.resolve([]))}
      managementRepo={managementRepo ?? makeManagementRepo()}
      playlistRepo={playlistRepo ?? makePlaylistRepo()}
    />
  );
}

// ─── Tests ────────────────────────────────────────────────────────────────────

describe("DashboardPage", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockUser = { email: "alice@example.com" };
    mockLoading = false;
    mockGetIdToken.mockResolvedValue("mock-token");
    mockSearchParamsGet = jest.fn().mockReturnValue(null);
  });

  // ─── Auth state ────────────────────────────────────────────────────────────

  it("returns null when auth is loading", () => {
    mockLoading = true;
    mockUser = null;
    const { container } = renderDashboard();
    expect(container.firstChild).toBeNull();
  });

  it("returns null and redirects to /login when not authenticated", async () => {
    mockUser = null;
    mockLoading = false;
    const { container } = renderDashboard();
    await waitFor(() => {
      expect(mockRouterReplace).toHaveBeenCalledWith("/login");
    });
    expect(container.firstChild).toBeNull();
  });

  it("renders the page heading for authenticated user", async () => {
    const repo = makeDashboardRepo(() => Promise.resolve([]));
    renderDashboard(repo);

    await waitFor(() => {
      expect(
        screen.getByRole("heading", { name: /my studio/i })
      ).toBeInTheDocument();
    });
  });

  // ─── Loading / empty states ────────────────────────────────────────────────

  it("shows loading text while fetching videos", async () => {
    // Use a never-resolving promise to keep the loading state.
    const repo = makeDashboardRepo(() => new Promise(() => {}));
    renderDashboard(repo);

    await waitFor(() => {
      expect(screen.getByText(/loading your videos/i)).toBeInTheDocument();
    });
  });

  it("shows empty state when user has no videos", async () => {
    const repo = makeDashboardRepo(() => Promise.resolve([]));
    renderDashboard(repo);

    await waitFor(() => {
      expect(
        screen.getByText(/you haven.t uploaded any videos yet/i)
      ).toBeInTheDocument();
    });
  });

  it("shows upload CTA link in empty state", async () => {
    const repo = makeDashboardRepo(() => Promise.resolve([]));
    renderDashboard(repo);

    await waitFor(() => {
      const links = screen.getAllByRole("link", { name: /upload/i });
      expect(links.length).toBeGreaterThan(0);
    });
  });

  // ─── Video list ────────────────────────────────────────────────────────────

  it("renders video titles in the table", async () => {
    const videos = [
      makeDashboardVideo({ id: "vid-1", title: "First Video" }),
      makeDashboardVideo({ id: "vid-2", title: "Second Video" }),
    ];
    const repo = makeDashboardRepo(() => Promise.resolve(videos));
    renderDashboard(repo);

    await waitFor(() => {
      expect(screen.getByText("First Video")).toBeInTheDocument();
      expect(screen.getByText("Second Video")).toBeInTheDocument();
    });
  });

  it("renders status badges for all statuses", async () => {
    const videos = [
      makeDashboardVideo({ id: "vid-1", status: "ready" }),
      makeDashboardVideo({ id: "vid-2", status: "processing" }),
      makeDashboardVideo({ id: "vid-3", status: "pending" }),
      makeDashboardVideo({ id: "vid-4", status: "failed" }),
    ];
    const repo = makeDashboardRepo(() => Promise.resolve(videos));
    renderDashboard(repo);

    await waitFor(() => {
      expect(screen.getByText("Ready")).toBeInTheDocument();
      expect(screen.getByText("Processing")).toBeInTheDocument();
      expect(screen.getByText("Pending")).toBeInTheDocument();
      expect(screen.getByText("Failed")).toBeInTheDocument();
    });
  });

  it("renders formatted view count", async () => {
    const repo = makeDashboardRepo(() =>
      Promise.resolve([makeDashboardVideo({ viewCount: 1234567 })])
    );
    renderDashboard(repo);

    await waitFor(() => {
      expect(screen.getByText("1,234,567")).toBeInTheDocument();
    });
  });

  it("renders a link to the video watch page for ready videos", async () => {
    const repo = makeDashboardRepo(() =>
      Promise.resolve([makeDashboardVideo({ id: "vid-1", title: "My Video", status: "ready" })])
    );
    renderDashboard(repo);

    await waitFor(() => {
      const link = screen.getByRole("link", { name: "My Video" });
      expect(link).toHaveAttribute("href", "/v/vid-1");
    });
  });

  it("does not link to watch page for non-ready videos", async () => {
    const repo = makeDashboardRepo(() =>
      Promise.resolve([makeDashboardVideo({ id: "vid-2", title: "Processing Video", status: "processing" })])
    );
    renderDashboard(repo);

    await waitFor(() => {
      expect(screen.getByText("Processing Video")).toBeInTheDocument();
    });
    // Should not be a link
    expect(screen.queryByRole("link", { name: "Processing Video" })).not.toBeInTheDocument();
  });

  it("renders Edit and Delete buttons for each video", async () => {
    const repo = makeDashboardRepo(() =>
      Promise.resolve([makeDashboardVideo({ title: "My Video" })])
    );
    renderDashboard(repo);

    await waitFor(() => {
      expect(screen.getByRole("button", { name: /edit my video/i })).toBeInTheDocument();
      expect(screen.getByRole("button", { name: /delete my video/i })).toBeInTheDocument();
    });
  });

  it("shows fetch error when listMyVideos throws", async () => {
    const repo = makeDashboardRepo(() => Promise.reject(new Error("network failure")));
    renderDashboard(repo);

    await waitFor(() => {
      expect(screen.getByRole("alert")).toHaveTextContent(/network failure/i);
    });
  });

  // ─── Upload banner ─────────────────────────────────────────────────────────

  it("shows upload success banner when ?uploaded param is present", async () => {
    mockSearchParamsGet = jest.fn().mockReturnValue("vid-new");
    const repo = makeDashboardRepo(() => Promise.resolve([]));
    renderDashboard(repo);

    await waitFor(() => {
      expect(screen.getByRole("status")).toHaveTextContent(/your video is being processed/i);
    });
  });

  it("does not show upload banner when ?uploaded param is absent", async () => {
    const repo = makeDashboardRepo(() => Promise.resolve([]));
    renderDashboard(repo);

    await waitFor(() => {
      expect(
        screen.getByText(/you haven.t uploaded any videos yet/i)
      ).toBeInTheDocument();
    });
    expect(screen.queryByRole("status")).not.toBeInTheDocument();
  });

  // ─── Upload new video CTA ──────────────────────────────────────────────────

  it("renders 'Upload new video' link pointing to /upload", async () => {
    const repo = makeDashboardRepo(() => Promise.resolve([]));
    renderDashboard(repo);

    await waitFor(() => {
      const link = screen.getByRole("link", { name: /upload new video/i });
      expect(link).toHaveAttribute("href", "/upload");
    });
  });

  // ─── Delete flow ───────────────────────────────────────────────────────────

  it("shows confirm/cancel buttons after clicking Delete", async () => {
    const user = userEvent.setup();
    const video = makeDashboardVideo({ title: "My Video" });
    const repo = makeDashboardRepo(() => Promise.resolve([video]));
    renderDashboard(repo);

    await waitFor(() =>
      expect(screen.getByRole("button", { name: /delete my video/i })).toBeInTheDocument()
    );

    await user.click(screen.getByRole("button", { name: /delete my video/i }));

    await waitFor(() => {
      expect(screen.getByRole("button", { name: /confirm/i })).toBeInTheDocument();
      expect(screen.getByRole("button", { name: /cancel/i })).toBeInTheDocument();
    });
  });

  it("removes video from list on successful delete", async () => {
    const user = userEvent.setup();
    const video = makeDashboardVideo({ id: "vid-1", title: "My Video" });
    const repo = makeDashboardRepo(() => Promise.resolve([video]));
    const management = makeManagementRepo({
      deleteVideo: jest.fn().mockResolvedValue(undefined),
    });
    renderDashboard(repo, management);

    await waitFor(() =>
      expect(screen.getByRole("button", { name: /delete my video/i })).toBeInTheDocument()
    );

    await user.click(screen.getByRole("button", { name: /delete my video/i }));
    await waitFor(() =>
      expect(screen.getByRole("button", { name: /confirm/i })).toBeInTheDocument()
    );

    await act(async () => {
      await user.click(screen.getByRole("button", { name: /confirm/i }));
    });

    await waitFor(() => {
      expect(screen.queryByText("My Video")).not.toBeInTheDocument();
    });
  });

  it("cancels delete confirmation and keeps video in list", async () => {
    const user = userEvent.setup();
    const video = makeDashboardVideo({ id: "vid-1", title: "My Video" });
    const repo = makeDashboardRepo(() => Promise.resolve([video]));
    renderDashboard(repo);

    await waitFor(() =>
      expect(screen.getByRole("button", { name: /delete my video/i })).toBeInTheDocument()
    );

    await user.click(screen.getByRole("button", { name: /delete my video/i }));
    await waitFor(() =>
      expect(screen.getByRole("button", { name: /cancel/i })).toBeInTheDocument()
    );
    await user.click(screen.getByRole("button", { name: /cancel/i }));

    await waitFor(() => {
      expect(screen.getByText("My Video")).toBeInTheDocument();
      expect(screen.getByRole("button", { name: /delete my video/i })).toBeInTheDocument();
    });
  });

  it("shows delete error when deleteVideo throws", async () => {
    const user = userEvent.setup();
    const video = makeDashboardVideo({ id: "vid-1", title: "My Video" });
    const repo = makeDashboardRepo(() => Promise.resolve([video]));
    const management = makeManagementRepo({
      deleteVideo: jest.fn().mockRejectedValue(new Error("forbidden")),
    });
    renderDashboard(repo, management);

    await waitFor(() =>
      expect(screen.getByRole("button", { name: /delete my video/i })).toBeInTheDocument()
    );

    await user.click(screen.getByRole("button", { name: /delete my video/i }));
    await waitFor(() =>
      expect(screen.getByRole("button", { name: /confirm/i })).toBeInTheDocument()
    );

    await act(async () => {
      await user.click(screen.getByRole("button", { name: /confirm/i }));
    });

    await waitFor(() => {
      expect(screen.getByRole("alert")).toHaveTextContent(/forbidden/i);
    });
  });

  // ─── Edit modal ────────────────────────────────────────────────────────────

  it("opens edit modal when Edit button is clicked", async () => {
    const user = userEvent.setup();
    const video = makeDashboardVideo({ title: "My Video" });
    const repo = makeDashboardRepo(() => Promise.resolve([video]));
    renderDashboard(repo);

    await waitFor(() =>
      expect(screen.getByRole("button", { name: /edit my video/i })).toBeInTheDocument()
    );

    await user.click(screen.getByRole("button", { name: /edit my video/i }));

    await waitFor(() => {
      expect(screen.getByRole("dialog")).toBeInTheDocument();
      expect(screen.getByRole("heading", { name: /edit video/i })).toBeInTheDocument();
    });
  });

  it("closes edit modal when Cancel is clicked", async () => {
    const user = userEvent.setup();
    const video = makeDashboardVideo({ title: "My Video" });
    const repo = makeDashboardRepo(() => Promise.resolve([video]));
    renderDashboard(repo);

    await waitFor(() =>
      expect(screen.getByRole("button", { name: /edit my video/i })).toBeInTheDocument()
    );

    await user.click(screen.getByRole("button", { name: /edit my video/i }));
    await waitFor(() =>
      expect(screen.getByRole("dialog")).toBeInTheDocument()
    );

    await user.click(screen.getByRole("button", { name: /cancel/i }));

    await waitFor(() => {
      expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    });
  });

  it("edit modal has title input pre-populated with current video title", async () => {
    const user = userEvent.setup();
    const video = makeDashboardVideo({ title: "Original Title" });
    const repo = makeDashboardRepo(() => Promise.resolve([video]));
    renderDashboard(repo);

    await waitFor(() =>
      expect(screen.getByRole("button", { name: /edit original title/i })).toBeInTheDocument()
    );

    await user.click(screen.getByRole("button", { name: /edit original title/i }));

    await waitFor(() => {
      const dialog = screen.getByRole("dialog");
      const titleInput = within(dialog).getByLabelText(/title/i) as HTMLInputElement;
      expect(titleInput.value).toBe("Original Title");
    });
  });

  it("calls updateVideo with correct params on save", async () => {
    const user = userEvent.setup();
    const video = makeDashboardVideo({ id: "vid-1", title: "Old Title" });
    const repo = makeDashboardRepo(() => Promise.resolve([video]));
    const updateVideoMock = jest.fn().mockResolvedValue({
      id: "vid-1", title: "New Title", description: null, status: "ready",
      thumbnailUrl: null, viewCount: 0, tags: ["new-tag"],
      uploader: { username: "alice", avatarUrl: null },
    } as UpdatedVideo);
    const management = makeManagementRepo({ updateVideo: updateVideoMock });
    renderDashboard(repo, management);

    await waitFor(() =>
      expect(screen.getByRole("button", { name: /edit old title/i })).toBeInTheDocument()
    );

    await user.click(screen.getByRole("button", { name: /edit old title/i }));
    await waitFor(() => expect(screen.getByRole("dialog")).toBeInTheDocument());

    // Clear title and type new one — scope to dialog to avoid matching table header
    const dialog = screen.getByRole("dialog");
    const titleInput = within(dialog).getByLabelText(/title/i);
    await user.clear(titleInput);
    await user.type(titleInput, "New Title");

    await user.type(within(dialog).getByLabelText(/tags/i), "new-tag");

    await act(async () => {
      await user.click(screen.getByRole("button", { name: /save changes/i }));
    });

    await waitFor(() => {
      expect(updateVideoMock).toHaveBeenCalledWith(
        "vid-1",
        expect.objectContaining({ title: "New Title" }),
        "mock-token"
      );
    });
  });

  it("closes edit modal after successful save", async () => {
    const user = userEvent.setup();
    const video = makeDashboardVideo({ title: "Old Title" });
    const repo = makeDashboardRepo(() => Promise.resolve([video]));
    const management = makeManagementRepo();
    renderDashboard(repo, management);

    await waitFor(() =>
      expect(screen.getByRole("button", { name: /edit old title/i })).toBeInTheDocument()
    );

    await user.click(screen.getByRole("button", { name: /edit old title/i }));
    await waitFor(() => expect(screen.getByRole("dialog")).toBeInTheDocument());

    await act(async () => {
      await user.click(screen.getByRole("button", { name: /save changes/i }));
    });

    await waitFor(() => {
      expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    });
  });

  it("shows error in modal when updateVideo throws", async () => {
    const user = userEvent.setup();
    const video = makeDashboardVideo({ title: "My Video" });
    const repo = makeDashboardRepo(() => Promise.resolve([video]));
    const management = makeManagementRepo({
      updateVideo: jest.fn().mockRejectedValue(new Error("title is required")),
    });
    renderDashboard(repo, management);

    await waitFor(() =>
      expect(screen.getByRole("button", { name: /edit my video/i })).toBeInTheDocument()
    );

    await user.click(screen.getByRole("button", { name: /edit my video/i }));
    await waitFor(() => expect(screen.getByRole("dialog")).toBeInTheDocument());

    await act(async () => {
      await user.click(screen.getByRole("button", { name: /save changes/i }));
    });

    await waitFor(() => {
      expect(screen.getByRole("alert")).toHaveTextContent(/title is required/i);
    });
    // Modal should still be open on error
    expect(screen.getByRole("dialog")).toBeInTheDocument();
  });

  it("edit modal has category select with expected options", async () => {
    const user = userEvent.setup();
    const video = makeDashboardVideo({ title: "My Video" });
    const repo = makeDashboardRepo(() => Promise.resolve([video]));
    renderDashboard(repo);

    await waitFor(() =>
      expect(screen.getByRole("button", { name: /edit my video/i })).toBeInTheDocument()
    );

    await user.click(screen.getByRole("button", { name: /edit my video/i }));
    await waitFor(() => expect(screen.getByRole("dialog")).toBeInTheDocument());

    const select = screen.getByLabelText(/category/i) as HTMLSelectElement;
    const options = Array.from(select.options).map((o) => o.text);
    expect(options).toContain("Education");
    expect(options).toContain("Entertainment");
    expect(options).toContain("Gaming");
    expect(options).toContain("Music");
    expect(options).toContain("Other");
  });

  it("passes correct params for updateVideo including categoryId", async () => {
    const user = userEvent.setup();
    const video = makeDashboardVideo({ id: "vid-1", title: "My Video" });
    const repo = makeDashboardRepo(() => Promise.resolve([video]));
    const updateVideoMock = jest.fn().mockResolvedValue({
      id: "vid-1", title: "My Video", description: null, status: "ready",
      thumbnailUrl: null, viewCount: 0, tags: [],
      uploader: { username: "alice", avatarUrl: null },
    } as UpdatedVideo);
    const management = makeManagementRepo({ updateVideo: updateVideoMock });
    renderDashboard(repo, management);

    await waitFor(() =>
      expect(screen.getByRole("button", { name: /edit my video/i })).toBeInTheDocument()
    );

    await user.click(screen.getByRole("button", { name: /edit my video/i }));
    await waitFor(() => expect(screen.getByRole("dialog")).toBeInTheDocument());

    await user.selectOptions(screen.getByLabelText(/category/i), "3");

    await act(async () => {
      await user.click(screen.getByRole("button", { name: /save changes/i }));
    });

    await waitFor(() => {
      const callParams: UpdateVideoParams = updateVideoMock.mock.calls[0][1];
      expect(callParams.categoryId).toBe(3);
    });
  });

  // ─── Playlists tab ─────────────────────────────────────────────────────────

  it("renders My videos and My playlists tab buttons", async () => {
    renderDashboard();

    await waitFor(() => {
      expect(screen.getByRole("button", { name: /my videos/i })).toBeInTheDocument();
      expect(screen.getByRole("button", { name: /my playlists/i })).toBeInTheDocument();
    });
  });

  it("shows playlists tab content when My playlists is clicked", async () => {
    const user = userEvent.setup();
    renderDashboard();

    await waitFor(() =>
      expect(screen.getByRole("button", { name: /my playlists/i })).toBeInTheDocument()
    );

    await user.click(screen.getByRole("button", { name: /my playlists/i }));

    await waitFor(() => {
      expect(screen.getByPlaceholderText(/new playlist title/i)).toBeInTheDocument();
    });
  });

  it("shows empty playlists state when user has no playlists", async () => {
    const user = userEvent.setup();
    const playlistRepo = makePlaylistRepo({
      listMine: jest.fn().mockResolvedValue([]),
    });
    renderDashboard(undefined, undefined, playlistRepo);

    await waitFor(() =>
      expect(screen.getByRole("button", { name: /my playlists/i })).toBeInTheDocument()
    );
    await user.click(screen.getByRole("button", { name: /my playlists/i }));

    await waitFor(() => {
      expect(screen.getByText(/you don.t have any playlists yet/i)).toBeInTheDocument();
    });
  });

  it("shows playlist titles when playlists exist", async () => {
    const user = userEvent.setup();
    const playlistRepo = makePlaylistRepo({
      listMine: jest.fn().mockResolvedValue([
        makePlaylist({ id: "pl-1", title: "Favourites" }),
        makePlaylist({ id: "pl-2", title: "Watch Later" }),
      ]),
    });
    renderDashboard(undefined, undefined, playlistRepo);

    await waitFor(() =>
      expect(screen.getByRole("button", { name: /my playlists/i })).toBeInTheDocument()
    );
    await user.click(screen.getByRole("button", { name: /my playlists/i }));

    await waitFor(() => {
      expect(screen.getByText("Favourites")).toBeInTheDocument();
      expect(screen.getByText("Watch Later")).toBeInTheDocument();
    });
  });

  it("creates a new playlist and shows it in the list", async () => {
    const user = userEvent.setup();
    const created = makePlaylist({ id: "pl-new", title: "New List" });
    const playlistRepo = makePlaylistRepo({
      listMine: jest.fn().mockResolvedValue([]),
      create: jest.fn().mockResolvedValue(created),
    });
    renderDashboard(undefined, undefined, playlistRepo);

    await waitFor(() =>
      expect(screen.getByRole("button", { name: /my playlists/i })).toBeInTheDocument()
    );
    await user.click(screen.getByRole("button", { name: /my playlists/i }));

    await waitFor(() =>
      expect(screen.getByPlaceholderText(/new playlist title/i)).toBeInTheDocument()
    );

    await user.type(screen.getByPlaceholderText(/new playlist title/i), "New List");

    await act(async () => {
      await user.click(screen.getByRole("button", { name: /create playlist/i }));
    });

    await waitFor(() => {
      expect(playlistRepo.create).toHaveBeenCalledWith("New List", "mock-token");
      expect(screen.getByText("New List")).toBeInTheDocument();
    });
  });

  it("shows rename input when Rename is clicked", async () => {
    const user = userEvent.setup();
    const playlistRepo = makePlaylistRepo({
      listMine: jest.fn().mockResolvedValue([makePlaylist({ title: "Old Name" })]),
    });
    renderDashboard(undefined, undefined, playlistRepo);

    await waitFor(() =>
      expect(screen.getByRole("button", { name: /my playlists/i })).toBeInTheDocument()
    );
    await user.click(screen.getByRole("button", { name: /my playlists/i }));

    await waitFor(() =>
      expect(screen.getByRole("button", { name: /rename old name/i })).toBeInTheDocument()
    );

    await user.click(screen.getByRole("button", { name: /rename old name/i }));

    expect(screen.getByDisplayValue("Old Name")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /^save$/i })).toBeInTheDocument();
  });

  it("saves renamed playlist title", async () => {
    const user = userEvent.setup();
    const updated = makePlaylist({ title: "New Name" });
    const playlistRepo = makePlaylistRepo({
      listMine: jest.fn().mockResolvedValue([makePlaylist({ title: "Old Name" })]),
      updateTitle: jest.fn().mockResolvedValue(updated),
    });
    renderDashboard(undefined, undefined, playlistRepo);

    await waitFor(() =>
      expect(screen.getByRole("button", { name: /my playlists/i })).toBeInTheDocument()
    );
    await user.click(screen.getByRole("button", { name: /my playlists/i }));

    await waitFor(() =>
      expect(screen.getByRole("button", { name: /rename old name/i })).toBeInTheDocument()
    );
    await user.click(screen.getByRole("button", { name: /rename old name/i }));

    const input = screen.getByDisplayValue("Old Name");
    await user.clear(input);
    await user.type(input, "New Name");

    await act(async () => {
      await user.click(screen.getByRole("button", { name: /^save$/i }));
    });

    await waitFor(() => {
      expect(playlistRepo.updateTitle).toHaveBeenCalledWith(
        "pl-1",
        "New Name",
        "mock-token"
      );
    });
  });

  it("shows delete confirm/cancel after clicking Delete on playlist", async () => {
    const user = userEvent.setup();
    const playlistRepo = makePlaylistRepo({
      listMine: jest.fn().mockResolvedValue([makePlaylist({ title: "Favourites" })]),
    });
    renderDashboard(undefined, undefined, playlistRepo);

    await waitFor(() =>
      expect(screen.getByRole("button", { name: /my playlists/i })).toBeInTheDocument()
    );
    await user.click(screen.getByRole("button", { name: /my playlists/i }));

    await waitFor(() =>
      expect(screen.getByRole("button", { name: /delete favourites/i })).toBeInTheDocument()
    );

    await user.click(screen.getByRole("button", { name: /delete favourites/i }));

    await waitFor(() => {
      expect(screen.getByRole("button", { name: /confirm/i })).toBeInTheDocument();
      expect(screen.getByRole("button", { name: /cancel/i })).toBeInTheDocument();
    });
  });

  it("removes playlist from list on successful delete", async () => {
    const user = userEvent.setup();
    const playlistRepo = makePlaylistRepo({
      listMine: jest.fn().mockResolvedValue([makePlaylist({ title: "Favourites" })]),
      deletePlaylist: jest.fn().mockResolvedValue(undefined),
    });
    renderDashboard(undefined, undefined, playlistRepo);

    await waitFor(() =>
      expect(screen.getByRole("button", { name: /my playlists/i })).toBeInTheDocument()
    );
    await user.click(screen.getByRole("button", { name: /my playlists/i }));

    await waitFor(() =>
      expect(screen.getByRole("button", { name: /delete favourites/i })).toBeInTheDocument()
    );
    await user.click(screen.getByRole("button", { name: /delete favourites/i }));

    await waitFor(() =>
      expect(screen.getByRole("button", { name: /confirm/i })).toBeInTheDocument()
    );

    await act(async () => {
      await user.click(screen.getByRole("button", { name: /confirm/i }));
    });

    await waitFor(() => {
      expect(screen.queryByText("Favourites")).not.toBeInTheDocument();
    });
  });
});
