/**
 * Test for error handling in VideoPlayer.
 * Reproduces MYTUBE-254: player should display error overlay when HLS manifest is unreachable.
 */
import React from "react";
import { render, act, screen } from "@testing-library/react";

// ─── Mock Video.js ────────────────────────────────────────────────────────────
const mockDispose = jest.fn();
let mockPlayerInstance: any = null;
let videoJsErrorCallback: ((error: any) => void) | null = null;
let videoJsLoadstartCallback: (() => void) | null = null;

const mockVideoJs = jest.fn((element: any, options: any) => {
  mockPlayerInstance = {
    dispose: mockDispose,
    on: jest.fn((event: string, callback: (error?: any) => void) => {
      if (event === "error") {
        videoJsErrorCallback = callback;
      } else if (event === "loadstart") {
        videoJsLoadstartCallback = callback as (() => void) | null;
      }
    }),
    error: jest.fn(() => ({
      code: 4,
      message: "MEDIA_ERR_SRC_NOT_SUPPORTED",
    })),
  };
  return mockPlayerInstance;
});

jest.mock("video.js", () => ({
  __esModule: true,
  default: mockVideoJs,
}));

jest.mock("@videojs/http-streaming", () => ({
  __esModule: true,
  default: {},
}));

jest.mock("video.js/dist/video-js.css", () => ({}), { virtual: true });

// ─── Import component AFTER mocks ─────────────────────────────────────────────
import VideoPlayer from "@/components/VideoPlayer";

// ─── Helpers ──────────────────────────────────────────────────────────────────
async function flushPromises(): Promise<void> {
  await act(async () => {
    await new Promise<void>((resolve) => setTimeout(resolve, 0));
  });
}

// ─── Tests ────────────────────────────────────────────────────────────────────
describe("VideoPlayer error handling (MYTUBE-254)", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockPlayerInstance = null;
    videoJsErrorCallback = null;
    videoJsLoadstartCallback = null;
  });

  it("displays error alert when HLS manifest fails to load", async () => {
    const unreachableUrl =
      "https://storage.googleapis.com/non-existent-bucket-12345/manifest.m3u8";

    const { container } = render(<VideoPlayer src={unreachableUrl} />);

    await flushPromises();

    // Simulate Video.js error event (manifest failed to load)
    await act(async () => {
      if (videoJsErrorCallback) {
        videoJsErrorCallback({
          code: 4,
          message: "MEDIA_ERR_SRC_NOT_SUPPORTED",
        });
      }
      await new Promise<void>((resolve) => setTimeout(resolve, 0));
    });

    // The component should display an error alert
    const errorAlert = screen.queryByRole("alert");
    expect(errorAlert).toBeInTheDocument();
    expect(errorAlert?.textContent).toMatch(/error|failed|network/i);
  });

  it("registers error event listener on Video.js player", async () => {
    render(<VideoPlayer src="https://cdn.example.com/videos/v1/index.m3u8" />);

    await flushPromises();

    // The component should register an error event listener
    expect(mockPlayerInstance?.on).toHaveBeenCalledWith(
      "error",
      expect.any(Function)
    );
  });

  it("keeps player container visible even when error occurs", async () => {
    const { container } = render(
      <VideoPlayer src="https://cdn.example.com/videos/v1/index.m3u8" />
    );

    await flushPromises();

    // Player container should be visible initially
    const playerContainer = container.querySelector("[data-vjs-player]");
    expect(playerContainer).toBeInTheDocument();

    // Simulate error
    await act(async () => {
      if (videoJsErrorCallback) {
        videoJsErrorCallback({
          code: 4,
          message: "MEDIA_ERR_SRC_NOT_SUPPORTED",
        });
      }
      await new Promise<void>((resolve) => setTimeout(resolve, 0));
    });

    // Player container should remain visible (not removed)
    expect(playerContainer).toBeInTheDocument();
  });

  it("clears error state when src prop changes", async () => {
    const { rerender } = render(
      <VideoPlayer src="https://cdn.example.com/videos/v1/index.m3u8" />
    );

    await flushPromises();

    // Simulate error on first video
    await act(async () => {
      if (videoJsErrorCallback) {
        videoJsErrorCallback({
          code: 4,
          message: "MEDIA_ERR_SRC_NOT_SUPPORTED",
        });
      }
      await new Promise<void>((resolve) => setTimeout(resolve, 0));
    });

    // Error should be visible
    let errorAlert = screen.queryByRole("alert");
    expect(errorAlert).toBeInTheDocument();

    // Change to a different video src
    rerender(<VideoPlayer src="https://cdn.example.com/videos/v2/index.m3u8" />);

    await flushPromises();

    // Error state should be cleared when new src is provided
    errorAlert = screen.queryByRole("alert");
    expect(errorAlert).not.toBeInTheDocument();
  });

  it("clears error state when loadstart event fires", async () => {
    render(<VideoPlayer src="https://cdn.example.com/videos/v1/index.m3u8" />);

    await flushPromises();

    // Simulate error
    await act(async () => {
      if (videoJsErrorCallback) {
        videoJsErrorCallback({
          code: 2,
          message: "MEDIA_ERR_NETWORK",
        });
      }
      await new Promise<void>((resolve) => setTimeout(resolve, 0));
    });

    // Error should be visible
    let errorAlert = screen.queryByRole("alert");
    expect(errorAlert).toBeInTheDocument();

    // Simulate loadstart event (playback retry)
    await act(async () => {
      if (videoJsLoadstartCallback) {
        videoJsLoadstartCallback();
      }
      await new Promise<void>((resolve) => setTimeout(resolve, 0));
    });

    // Error state should be cleared when loadstart fires
    errorAlert = screen.queryByRole("alert");
    expect(errorAlert).not.toBeInTheDocument();
  });
});
