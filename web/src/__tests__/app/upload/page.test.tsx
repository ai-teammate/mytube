/**
 * Unit tests for src/app/upload/page.tsx
 * Covers: upload form, progress bar, error handling, session expiry,
 *         and the library area (loading, filtering, sorting, empty/error states).
 */
import React from "react";
import { render, screen, waitFor, act } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

// ─── Mock next/navigation ─────────────────────────────────────────────────────

const mockRouterReplace = jest.fn();
const mockRouterPush = jest.fn();
jest.mock("next/navigation", () => ({
  useRouter: () => ({ replace: mockRouterReplace, push: mockRouterPush }),
  usePathname: () => "/upload",
  useSearchParams: () => null,
}));

// ─── Mock next/image ──────────────────────────────────────────────────────────

jest.mock("next/image", () => ({
  __esModule: true,
  default: function MockImage({
    src,
    alt,
    ...props
  }: {
    src: string;
    alt: string;
    [key: string]: unknown;
  }) {
    // eslint-disable-next-line @typescript-eslint/no-unused-vars
    const { fill: _fill, ...rest } = props;
    // eslint-disable-next-line @next/next/no-img-element
    return <img src={src} alt={alt} {...rest} />;
  },
}));

// ─── Mock AuthContext ─────────────────────────────────────────────────────────

let mockUser: { email: string; displayName: string | null } | null = null;
let mockLoading = false;
const mockGetIdToken = jest.fn().mockResolvedValue("mock-token");

jest.mock("@/context/AuthContext", () => ({
  useAuth: () => ({
    user: mockUser,
    loading: mockLoading,
    getIdToken: mockGetIdToken,
  }),
}));

// ─── Mock ApiVideoUploadRepository ───────────────────────────────────────────

let _mockInitiateUpload: jest.Mock = jest.fn();

jest.mock("@/data/videoUploadRepository", () => ({
  ApiVideoUploadRepository: jest.fn().mockImplementation(() => ({
    initiateUpload: (...args: unknown[]) => _mockInitiateUpload(...args),
  })),
}));

// ─── Mock ApiDashboardVideoRepository ────────────────────────────────────────

let _mockListMyVideos: jest.Mock = jest.fn();

jest.mock("@/data/dashboardRepository", () => ({
  ApiDashboardVideoRepository: jest.fn().mockImplementation(() => ({
    listMyVideos: (...args: unknown[]) => _mockListMyVideos(...args),
  })),
}));

// ─── Mock XMLHttpRequest ──────────────────────────────────────────────────────

interface MockXHRInstance {
  upload: { onprogress: ((e: ProgressEvent) => void) | null };
  onload: (() => void) | null;
  onerror: (() => void) | null;
  open: jest.Mock;
  setRequestHeader: jest.Mock;
  send: jest.Mock;
  status: number;
  simulateProgress(loaded: number, total: number): void;
  simulateLoad(status?: number): void;
  simulateError(): void;
}

let mockXHRInstances: MockXHRInstance[] = [];

function createMockXHR(): MockXHRInstance {
  const instance: MockXHRInstance = {
    upload: { onprogress: null },
    onload: null,
    onerror: null,
    open: jest.fn(),
    setRequestHeader: jest.fn(),
    send: jest.fn(),
    status: 200,
    simulateProgress(loaded, total) {
      instance.upload.onprogress?.({
        lengthComputable: true,
        loaded,
        total,
      } as ProgressEvent);
    },
    simulateLoad(status = 200) {
      instance.status = status;
      instance.onload?.();
    },
    simulateError() {
      instance.onerror?.();
    },
  };
  return instance;
}

const OriginalXHR = global.XMLHttpRequest;
beforeAll(() => {
  (global as unknown as Record<string, unknown>).XMLHttpRequest = jest.fn(
    () => {
      const xhr = createMockXHR();
      mockXHRInstances.push(xhr);
      return xhr;
    }
  );
});

afterAll(() => {
  (global as unknown as Record<string, unknown>).XMLHttpRequest = OriginalXHR;
});

// ─── Import page AFTER mocks ──────────────────────────────────────────────────

import UploadPage from "@/app/upload/page";

// ─── Helpers ─────────────────────────────────────────────────────────────────

function makeVideoFile(name = "test.mp4", type = "video/mp4", size = 1024) {
  return new File([new ArrayBuffer(size)], name, { type });
}

import type { DashboardVideo } from "@/domain/dashboard";

function makeDashboardVideo(overrides: Partial<DashboardVideo> = {}): DashboardVideo {
  return {
    id: "vid-1",
    title: "My Test Video",
    status: "ready",
    thumbnailUrl: null,
    viewCount: 42,
    createdAt: "2024-06-01T10:00:00Z",
    description: null,
    categoryId: null,
    tags: [],
    ...overrides,
  };
}

// ─── Tests ────────────────────────────────────────────────────────────────────

describe("UploadPage", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    _mockInitiateUpload = jest.fn().mockResolvedValue({
      videoId: "vid-123",
      uploadUrl: "https://storage.googleapis.com/bucket/raw/uid/vid-123?sig=x",
    });
    _mockListMyVideos = jest.fn().mockResolvedValue([]);
    mockXHRInstances = [];
    mockUser = { email: "alice@example.com", displayName: "alice" };
    mockLoading = false;
    mockGetIdToken.mockResolvedValue("mock-token");
  });

  // ─── Auth state ────────────────────────────────────────────────────────────

  it("renders loading spinner when loading=true", () => {
    mockLoading = true;
    mockUser = null;
    render(<UploadPage />);
    expect(screen.getByText(/loading/i)).toBeInTheDocument();
  });

  it("redirects to /login?next=/upload when not authenticated and not loading", async () => {
    mockUser = null;
    mockLoading = false;
    render(<UploadPage />);
    await waitFor(() => {
      expect(mockRouterReplace).toHaveBeenCalledWith("/login?next=%2Fupload");
    });
  });

  it("renders the upload form for authenticated user", async () => {
    render(<UploadPage />);
    await waitFor(() => {
      expect(
        screen.getByRole("heading", { name: /personal video upload/i, level: 2 })
      ).toBeInTheDocument();
    });
    expect(screen.getByLabelText(/video file/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/title/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/description/i)).toBeInTheDocument();
    expect(screen.getByLabelText("Category")).toBeInTheDocument();
    expect(screen.getByLabelText(/tags/i)).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /upload video/i })
    ).toBeInTheDocument();
  });

  // ─── File picker ───────────────────────────────────────────────────────────

  it("shows mime type error when non-video file is selected", async () => {
    render(<UploadPage />);
    await waitFor(() =>
      expect(screen.getByLabelText(/video file/i)).toBeInTheDocument()
    );

    const imageFile = new File(["img"], "photo.jpg", { type: "image/jpeg" });
    const input = screen.getByLabelText(/video file/i) as HTMLInputElement;
    await act(async () => {
      Object.defineProperty(input, "files", {
        value: [imageFile],
        configurable: true,
      });
      input.dispatchEvent(new Event("change", { bubbles: true }));
    });

    await waitFor(() => {
      expect(screen.getAllByRole("alert")[0]).toHaveTextContent(
        /unsupported file type/i
      );
    });
  });

  it("shows file size warning for files over 4 GB", async () => {
    const user = userEvent.setup();
    render(<UploadPage />);
    await waitFor(() =>
      expect(screen.getByLabelText(/video file/i)).toBeInTheDocument()
    );

    const largeFile = makeVideoFile("large.mp4", "video/mp4", 100);
    Object.defineProperty(largeFile, "size", {
      value: 4 * 1024 * 1024 * 1024 + 1,
    });

    await user.upload(screen.getByLabelText(/video file/i), largeFile);

    await waitFor(() => {
      expect(screen.getByRole("note")).toHaveTextContent(/larger than 4\.0 GB/i);
    });
  });

  it("shows no size warning for files under 4 GB", async () => {
    const user = userEvent.setup();
    render(<UploadPage />);
    await waitFor(() =>
      expect(screen.getByLabelText(/video file/i)).toBeInTheDocument()
    );

    const smallFile = makeVideoFile("small.mp4", "video/mp4", 1024);
    await user.upload(screen.getByLabelText(/video file/i), smallFile);

    await waitFor(() => {
      expect(screen.queryByRole("note")).not.toBeInTheDocument();
    });
  });

  // ─── Form validation ───────────────────────────────────────────────────────

  it("shows error when submit is clicked with no file selected", async () => {
    const user = userEvent.setup();
    render(<UploadPage />);
    await waitFor(() =>
      expect(screen.getByRole("button", { name: /upload video/i })).toBeInTheDocument()
    );

    await user.type(screen.getByLabelText(/title/i), "My Video");
    await user.click(screen.getByRole("button", { name: /upload video/i }));

    await waitFor(() => {
      expect(screen.getByRole("alert")).toHaveTextContent(
        /please select a video file/i
      );
    });
  });

  it("shows auth error when getIdToken returns null on submit", async () => {
    mockGetIdToken.mockResolvedValue(null);
    const user = userEvent.setup();
    render(<UploadPage />);
    await waitFor(() =>
      expect(screen.getByLabelText(/video file/i)).toBeInTheDocument()
    );

    const videoFile = makeVideoFile();
    await user.upload(screen.getByLabelText(/video file/i), videoFile);
    await user.type(screen.getByLabelText(/title/i), "My Video");
    await user.click(screen.getByRole("button", { name: /upload video/i }));

    await waitFor(() => {
      expect(screen.getByRole("alert")).toHaveTextContent(
        /not authenticated/i
      );
    });
  });

  // ─── Upload flow ───────────────────────────────────────────────────────────

  it("calls initiateUpload with correct params on submit", async () => {
    const user = userEvent.setup();
    render(<UploadPage />);
    await waitFor(() =>
      expect(screen.getByLabelText(/video file/i)).toBeInTheDocument()
    );

    const videoFile = makeVideoFile("myvideo.mp4", "video/mp4");
    await user.upload(screen.getByLabelText(/video file/i), videoFile);
    await user.type(screen.getByLabelText(/title/i), "My Video");
    await user.type(screen.getByLabelText(/description/i), "A description");
    await user.selectOptions(screen.getByLabelText("Category"), "3");
    await user.type(screen.getByLabelText(/tags/i), "go, tutorial");

    await act(async () => {
      await user.click(screen.getByRole("button", { name: /upload video/i }));
    });

    await waitFor(() => {
      expect(_mockInitiateUpload).toHaveBeenCalledWith(
        expect.objectContaining({
          title: "My Video",
          description: "A description",
          categoryId: 3,
          tags: ["go", "tutorial"],
        }),
        "mock-token"
      );
    });
  });

  it("sends the PUT request to the signed upload URL via XHR", async () => {
    const user = userEvent.setup();
    render(<UploadPage />);
    await waitFor(() =>
      expect(screen.getByLabelText(/video file/i)).toBeInTheDocument()
    );

    const videoFile = makeVideoFile();
    await user.upload(screen.getByLabelText(/video file/i), videoFile);
    await user.type(screen.getByLabelText(/title/i), "My Video");

    await act(async () => {
      await user.click(screen.getByRole("button", { name: /upload video/i }));
    });

    await waitFor(() => expect(mockXHRInstances.length).toBeGreaterThan(0));

    const xhr = mockXHRInstances[0];
    expect(xhr.open).toHaveBeenCalledWith(
      "PUT",
      "https://storage.googleapis.com/bucket/raw/uid/vid-123?sig=x"
    );
    expect(xhr.setRequestHeader).toHaveBeenCalledWith(
      "Content-Type",
      "video/mp4"
    );
    expect(xhr.send).toHaveBeenCalledWith(videoFile);
  });

  it("shows progress bar during upload", async () => {
    const user = userEvent.setup();
    render(<UploadPage />);
    await waitFor(() =>
      expect(screen.getByLabelText(/video file/i)).toBeInTheDocument()
    );

    const videoFile = makeVideoFile();
    await user.upload(screen.getByLabelText(/video file/i), videoFile);
    await user.type(screen.getByLabelText(/title/i), "My Video");

    await act(async () => {
      await user.click(screen.getByRole("button", { name: /upload video/i }));
    });

    await waitFor(() => expect(mockXHRInstances.length).toBeGreaterThan(0));

    await act(async () => {
      mockXHRInstances[0].simulateProgress(50, 100);
    });

    await waitFor(() => {
      expect(screen.getByRole("progressbar")).toBeInTheDocument();
      expect(screen.getByText("50%")).toBeInTheDocument();
    });
  });

  it("redirects to dashboard after successful upload", async () => {
    const user = userEvent.setup();
    render(<UploadPage />);
    await waitFor(() =>
      expect(screen.getByLabelText(/video file/i)).toBeInTheDocument()
    );

    const videoFile = makeVideoFile();
    await user.upload(screen.getByLabelText(/video file/i), videoFile);
    await user.type(screen.getByLabelText(/title/i), "My Video");

    await act(async () => {
      await user.click(screen.getByRole("button", { name: /upload video/i }));
    });

    await waitFor(() => expect(mockXHRInstances.length).toBeGreaterThan(0));

    await act(async () => {
      mockXHRInstances[0].simulateLoad(200);
    });

    await waitFor(() => {
      expect(mockRouterReplace).toHaveBeenCalledWith(
        expect.stringContaining("uploaded=vid-123")
      );
    });
  });

  it("shows error when initiateUpload throws", async () => {
    _mockInitiateUpload.mockRejectedValue(
      new Error("title is required")
    );
    const user = userEvent.setup();
    render(<UploadPage />);
    await waitFor(() =>
      expect(screen.getByLabelText(/video file/i)).toBeInTheDocument()
    );

    const videoFile = makeVideoFile();
    await user.upload(screen.getByLabelText(/video file/i), videoFile);
    await user.type(screen.getByLabelText(/title/i), "My Video");
    await user.click(screen.getByRole("button", { name: /upload video/i }));

    await waitFor(() => {
      expect(screen.getByRole("alert")).toHaveTextContent(/title is required/i);
    });
  });

  it("shows error when GCS PUT request fails with non-2xx status", async () => {
    const user = userEvent.setup();
    render(<UploadPage />);
    await waitFor(() =>
      expect(screen.getByLabelText(/video file/i)).toBeInTheDocument()
    );

    const videoFile = makeVideoFile();
    await user.upload(screen.getByLabelText(/video file/i), videoFile);
    await user.type(screen.getByLabelText(/title/i), "My Video");

    await act(async () => {
      await user.click(screen.getByRole("button", { name: /upload video/i }));
    });

    await waitFor(() => expect(mockXHRInstances.length).toBeGreaterThan(0));

    await act(async () => {
      mockXHRInstances[0].simulateLoad(403);
    });

    await waitFor(() => {
      expect(screen.getByRole("alert")).toHaveTextContent(/GCS upload failed/i);
    });
  });

  it("shows error on XHR network error", async () => {
    const user = userEvent.setup();
    render(<UploadPage />);
    await waitFor(() =>
      expect(screen.getByLabelText(/video file/i)).toBeInTheDocument()
    );

    const videoFile = makeVideoFile();
    await user.upload(screen.getByLabelText(/video file/i), videoFile);
    await user.type(screen.getByLabelText(/title/i), "My Video");

    await act(async () => {
      await user.click(screen.getByRole("button", { name: /upload video/i }));
    });

    await waitFor(() => expect(mockXHRInstances.length).toBeGreaterThan(0));

    await act(async () => {
      mockXHRInstances[0].simulateError();
    });

    await waitFor(() => {
      expect(screen.getByRole("alert")).toHaveTextContent(
        /network error during upload/i
      );
    });
  });

  it("displays accepted formats note", async () => {
    render(<UploadPage />);
    await waitFor(() => {
      expect(
        screen.getByText(/supported formats.*mp4.*mov.*avi.*webm/i)
      ).toBeInTheDocument();
    });
  });

  it("shows category options in the upload form dropdown", async () => {
    render(<UploadPage />);
    await waitFor(() =>
      expect(screen.getByLabelText("Category")).toBeInTheDocument()
    );

    const select = screen.getByLabelText("Category") as HTMLSelectElement;
    const optionValues = Array.from(select.options).map((o) => o.text);
    expect(optionValues).toContain("Education");
    expect(optionValues).toContain("Gaming");
    expect(optionValues).toContain("Music");
  });

  // ─── Session expiration ────────────────────────────────────────────────────

  it("redirects to login when session expires after GCS upload completes", async () => {
    // The library useEffect calls getIdToken on mount (call #1).
    // handleSubmit calls getIdToken before the upload (call #2).
    // After GCS upload completes, getIdToken is called again (call #3) to
    // verify the session — this one simulates expiry by returning null.
    let getIdTokenCallCount = 0;
    mockGetIdToken.mockImplementation(async () => {
      getIdTokenCallCount++;
      return getIdTokenCallCount < 3 ? "mock-token" : null;
    });

    const user = userEvent.setup();
    render(<UploadPage />);
    await waitFor(() =>
      expect(screen.getByLabelText(/video file/i)).toBeInTheDocument()
    );

    const videoFile = makeVideoFile();
    await user.upload(screen.getByLabelText(/video file/i), videoFile);
    await user.type(screen.getByLabelText(/title/i), "My Video");

    await act(async () => {
      await user.click(screen.getByRole("button", { name: /upload video/i }));
    });

    await waitFor(() => expect(mockXHRInstances.length).toBeGreaterThan(0));

    await act(async () => {
      mockXHRInstances[0].simulateLoad(200);
    });

    await waitFor(() => {
      expect(mockRouterReplace).toHaveBeenCalledWith("/login");
    });

    expect(mockRouterReplace).not.toHaveBeenCalledWith(
      expect.stringContaining("/dashboard")
    );
  });

  // ─── Library area ──────────────────────────────────────────────────────────

  it("renders the library section heading", async () => {
    render(<UploadPage />);
    await waitFor(() => {
      expect(
        screen.getByRole("heading", { name: /recently uploaded/i, level: 3 })
      ).toBeInTheDocument();
    });
  });

  it("shows loading state while library is being fetched", async () => {
    // Library fetch never resolves during this test
    _mockListMyVideos.mockReturnValue(new Promise(() => {}));
    render(<UploadPage />);
    await waitFor(() => {
      expect(screen.getByText(/loading videos/i)).toBeInTheDocument();
    });
  });

  it("renders VideoCards when library loads successfully", async () => {
    _mockListMyVideos.mockResolvedValue([
      makeDashboardVideo({ id: "v1", title: "My First Video" }),
      makeDashboardVideo({ id: "v2", title: "My Second Video" }),
    ]);
    render(<UploadPage />);
    await waitFor(() => {
      expect(screen.getByText("My First Video")).toBeInTheDocument();
      expect(screen.getByText("My Second Video")).toBeInTheDocument();
    });
  });

  it("shows empty-state message when user has no videos", async () => {
    _mockListMyVideos.mockResolvedValue([]);
    render(<UploadPage />);
    await waitFor(() => {
      expect(
        screen.getByText(/no videos yet/i)
      ).toBeInTheDocument();
    });
  });

  it("shows error message when library fetch fails", async () => {
    _mockListMyVideos.mockRejectedValue(new Error("Network failure"));
    render(<UploadPage />);
    await waitFor(() => {
      const alerts = screen.getAllByRole("alert");
      const libAlert = alerts.find((el) =>
        el.textContent?.includes("Network failure")
      );
      expect(libAlert).toBeInTheDocument();
    });
  });

  it("calls listMyVideos with the auth token", async () => {
    render(<UploadPage />);
    await waitFor(() => {
      expect(_mockListMyVideos).toHaveBeenCalledWith("mock-token");
    });
  });

  it("filters videos by search query (title match)", async () => {
    _mockListMyVideos.mockResolvedValue([
      makeDashboardVideo({ id: "v1", title: "Go Tutorial" }),
      makeDashboardVideo({ id: "v2", title: "React Basics" }),
    ]);
    const user = userEvent.setup();
    render(<UploadPage />);

    await waitFor(() => {
      expect(screen.getByText("Go Tutorial")).toBeInTheDocument();
    });

    await user.type(screen.getByRole("searchbox", { name: /search videos/i }), "React");

    await waitFor(() => {
      expect(screen.queryByText("Go Tutorial")).not.toBeInTheDocument();
      expect(screen.getByText("React Basics")).toBeInTheDocument();
    });
  });

  it("filters videos by search query (tag match)", async () => {
    _mockListMyVideos.mockResolvedValue([
      makeDashboardVideo({ id: "v1", title: "Video A", tags: ["golang", "backend"] }),
      makeDashboardVideo({ id: "v2", title: "Video B", tags: ["react", "frontend"] }),
    ]);
    const user = userEvent.setup();
    render(<UploadPage />);

    await waitFor(() => {
      expect(screen.getByText("Video A")).toBeInTheDocument();
    });

    await user.type(screen.getByRole("searchbox", { name: /search videos/i }), "golang");

    await waitFor(() => {
      expect(screen.getByText("Video A")).toBeInTheDocument();
      expect(screen.queryByText("Video B")).not.toBeInTheDocument();
    });
  });

  it("filters videos by category", async () => {
    _mockListMyVideos.mockResolvedValue([
      makeDashboardVideo({ id: "v1", title: "Education Video", categoryId: 1 }),
      makeDashboardVideo({ id: "v2", title: "Gaming Video", categoryId: 3 }),
    ]);
    const user = userEvent.setup();
    render(<UploadPage />);

    await waitFor(() => {
      expect(screen.getByText("Education Video")).toBeInTheDocument();
    });

    await user.selectOptions(
      screen.getByRole("combobox", { name: /filter by category/i }),
      "3"
    );

    await waitFor(() => {
      expect(screen.queryByText("Education Video")).not.toBeInTheDocument();
      expect(screen.getByText("Gaming Video")).toBeInTheDocument();
    });
  });

  it("shows no-match message when filters return empty results", async () => {
    _mockListMyVideos.mockResolvedValue([
      makeDashboardVideo({ id: "v1", title: "Go Tutorial" }),
    ]);
    const user = userEvent.setup();
    render(<UploadPage />);

    await waitFor(() => {
      expect(screen.getByText("Go Tutorial")).toBeInTheDocument();
    });

    await user.type(
      screen.getByRole("searchbox", { name: /search videos/i }),
      "xyzzy"
    );

    await waitFor(() => {
      expect(
        screen.getByText(/no videos match your filters/i)
      ).toBeInTheDocument();
    });
  });

  it("resets search and category filter when Reset button is clicked", async () => {
    _mockListMyVideos.mockResolvedValue([
      makeDashboardVideo({ id: "v1", title: "Go Tutorial", categoryId: 3 }),
    ]);
    const user = userEvent.setup();
    render(<UploadPage />);

    await waitFor(() => {
      expect(screen.getByText("Go Tutorial")).toBeInTheDocument();
    });

    // Apply filters
    await user.type(
      screen.getByRole("searchbox", { name: /search videos/i }),
      "React"
    );
    await waitFor(() => {
      expect(screen.getByText(/no videos match/i)).toBeInTheDocument();
    });

    // Reset
    await user.click(screen.getByRole("button", { name: /reset/i }));

    await waitFor(() => {
      expect(screen.getByText("Go Tutorial")).toBeInTheDocument();
    });
    expect(
      (screen.getByRole("searchbox", { name: /search videos/i }) as HTMLInputElement).value
    ).toBe("");
  });

  it("toggles sort order between Newest first and Oldest first", async () => {
    const user = userEvent.setup();
    render(<UploadPage />);
    await waitFor(() => {
      expect(screen.getByText(/newest first/i)).toBeInTheDocument();
    });

    await user.click(screen.getByText(/newest first/i));

    await waitFor(() => {
      expect(screen.getByText(/oldest first/i)).toBeInTheDocument();
    });

    await user.click(screen.getByText(/oldest first/i));

    await waitFor(() => {
      expect(screen.getByText(/newest first/i)).toBeInTheDocument();
    });
  });

  it("sorts videos newest first by default", async () => {
    _mockListMyVideos.mockResolvedValue([
      makeDashboardVideo({ id: "v1", title: "Old Video", createdAt: "2024-01-01T00:00:00Z" }),
      makeDashboardVideo({ id: "v2", title: "New Video", createdAt: "2024-06-01T00:00:00Z" }),
    ]);
    render(<UploadPage />);

    await waitFor(() => {
      expect(screen.getByText("New Video")).toBeInTheDocument();
      expect(screen.getByText("Old Video")).toBeInTheDocument();
    });

    const cards = screen.getAllByRole("link", { name: /video/i });
    // New Video link should appear before Old Video link in the DOM
    const newIndex = cards.findIndex((el) => el.textContent?.includes("New Video"));
    const oldIndex = cards.findIndex((el) => el.textContent?.includes("Old Video"));
    expect(newIndex).toBeLessThan(oldIndex);
  });

  it("sorts videos oldest first after toggling sort order", async () => {
    _mockListMyVideos.mockResolvedValue([
      makeDashboardVideo({ id: "v1", title: "Old Video", createdAt: "2024-01-01T00:00:00Z" }),
      makeDashboardVideo({ id: "v2", title: "New Video", createdAt: "2024-06-01T00:00:00Z" }),
    ]);
    const user = userEvent.setup();
    render(<UploadPage />);

    await waitFor(() => {
      expect(screen.getByText("New Video")).toBeInTheDocument();
    });

    await user.click(screen.getByText(/newest first/i));

    await waitFor(() => {
      expect(screen.getByText(/oldest first/i)).toBeInTheDocument();
    });

    const cards = screen.getAllByRole("link", { name: /video/i });
    const newIndex = cards.findIndex((el) => el.textContent?.includes("New Video"));
    const oldIndex = cards.findIndex((el) => el.textContent?.includes("Old Video"));
    expect(oldIndex).toBeLessThan(newIndex);
  });

  it("renders toolbar with search, category filter, and reset controls", async () => {
    render(<UploadPage />);
    await waitFor(() => {
      expect(
        screen.getByRole("searchbox", { name: /search videos/i })
      ).toBeInTheDocument();
      expect(
        screen.getByRole("combobox", { name: /filter by category/i })
      ).toBeInTheDocument();
      expect(
        screen.getByRole("button", { name: /reset/i })
      ).toBeInTheDocument();
    });
  });

  it("uses the uploader username derived from user email for library VideoCards", async () => {
    mockUser = { email: "testuser@example.com", displayName: null };
    _mockListMyVideos.mockResolvedValue([
      makeDashboardVideo({ id: "v1", title: "My Video" }),
    ]);
    render(<UploadPage />);
    await waitFor(() => {
      expect(screen.getByText("My Video")).toBeInTheDocument();
    });
    // Username link in VideoCard sub-line
    expect(screen.getByText("testuser")).toBeInTheDocument();
  });
});
