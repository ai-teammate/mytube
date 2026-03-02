/**
 * Unit tests for src/app/upload/page.tsx
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
// jest.mock factories are hoisted to the top of the file, so they cannot close
// over variables declared with const/let. We use a module-level variable that
// is mutated inside beforeEach and read by the mock implementation via a
// function call, which is evaluated at call time (not at mock construction time).

let _mockInitiateUpload: jest.Mock = jest.fn();

jest.mock("@/data/videoUploadRepository", () => ({
  ApiVideoUploadRepository: jest.fn().mockImplementation(() => ({
    // Forward to _mockInitiateUpload lazily so beforeEach resets work.
    initiateUpload: (...args: unknown[]) => _mockInitiateUpload(...args),
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

// ─── Tests ────────────────────────────────────────────────────────────────────

describe("UploadPage", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    // Re-create the mock function so clearAllMocks + per-test overrides work.
    _mockInitiateUpload = jest.fn().mockResolvedValue({
      videoId: "vid-123",
      uploadUrl: "https://storage.googleapis.com/bucket/raw/uid/vid-123?sig=x",
    });
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

  it("redirects to /login when not authenticated and not loading", async () => {
    mockUser = null;
    mockLoading = false;
    render(<UploadPage />);
    await waitFor(() => {
      expect(mockRouterReplace).toHaveBeenCalledWith("/login");
    });
  });

  it("renders the upload form for authenticated user", async () => {
    render(<UploadPage />);
    await waitFor(() => {
      expect(
        screen.getByRole("heading", { name: /upload video/i })
      ).toBeInTheDocument();
    });
    expect(screen.getByLabelText(/video file/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/title/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/description/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/category/i)).toBeInTheDocument();
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

    // Use fireEvent directly so the accept attribute does not filter out the
    // non-video file before our MIME-type validation in the change handler runs.
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
      expect(screen.getByRole("alert")).toHaveTextContent(
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
    await user.selectOptions(screen.getByLabelText(/category/i), "3");
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

  it("redirects to user page after successful upload", async () => {
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

  it("shows category options in the dropdown", async () => {
    render(<UploadPage />);
    await waitFor(() =>
      expect(screen.getByLabelText(/category/i)).toBeInTheDocument()
    );

    const select = screen.getByLabelText(/category/i) as HTMLSelectElement;
    const optionValues = Array.from(select.options).map((o) => o.text);
    expect(optionValues).toContain("Education");
    expect(optionValues).toContain("Gaming");
    expect(optionValues).toContain("Music");
  });
});
