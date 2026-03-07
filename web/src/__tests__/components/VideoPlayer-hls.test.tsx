/**
 * Reproduction test for MYTUBE-243:
 * Video.js player fails to initialize or play HLS stream on public video watch page.
 *
 * This test verifies that the VideoPlayer component imports @videojs/http-streaming
 * plugin, which is required for HLS playback on non-Safari browsers.
 */
import React from "react";
import { render, act } from "@testing-library/react";

// ─── Mock video.js and http-streaming ─────────────────────────────────────────
const mockDispose = jest.fn();
const mockPlayerInstance = { dispose: mockDispose };
const mockVideoJs = jest.fn(() => mockPlayerInstance);

jest.mock("video.js", () => ({
  __esModule: true,
  default: mockVideoJs,
}));

// Track whether http-streaming was imported
let httpStreamingImported = false;
jest.mock("@videojs/http-streaming", () => {
  httpStreamingImported = true;
  return {
    __esModule: true,
    default: {},
  };
});

jest.mock("video.js/dist/video-js.css", () => ({}), { virtual: true });

// ─── Import component AFTER mocks ─────────────────────────────────────────────
import VideoPlayer from "@/components/VideoPlayer";

// ─── Helpers ──────────────────────────────────────────────────────────────────
async function flushPromises(): Promise<void> {
  await act(async () => {
    await new Promise<void>((resolve) => setTimeout(resolve, 0));
  });
}

// ─── Test ─────────────────────────────────────────────────────────────────────
describe("VideoPlayer HLS support (MYTUBE-243)", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    httpStreamingImported = false;
  });

  it("imports @videojs/http-streaming plugin for HLS playback on non-Safari browsers", async () => {
    render(
      <VideoPlayer src="https://cdn.example.com/videos/v1/index.m3u8" />
    );

    await flushPromises();

    // The component should import @videojs/http-streaming during initialization
    // to enable HLS playback on Chrome, Firefox, Edge, etc.
    expect(httpStreamingImported).toBe(true);
  });
});
