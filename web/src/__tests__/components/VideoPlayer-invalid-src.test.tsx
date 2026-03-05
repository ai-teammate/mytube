/**
 * Test for invalid src handling in VideoPlayer.
 * Reproduces MYTUBE-245: player should not initialize with empty or invalid src.
 */
import React from "react";
import { render, act } from "@testing-library/react";

const mockDispose = jest.fn();
const mockPlayerInstance = { dispose: mockDispose };
const mockVideoJs = jest.fn(() => mockPlayerInstance);

jest.mock("video.js", () => ({
  __esModule: true,
  default: mockVideoJs,
}));

jest.mock("@videojs/http-streaming", () => ({
  __esModule: true,
  default: {},
}));

jest.mock("video.js/dist/video-js.css", () => ({}), { virtual: true });

import VideoPlayer from "@/components/VideoPlayer";

async function flushPromises(): Promise<void> {
  await act(async () => {
    await new Promise<void>((resolve) => setTimeout(resolve, 0));
  });
}

describe("VideoPlayer invalid src handling", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it("does not initialize player with empty string src", async () => {
    render(<VideoPlayer src="" />);

    await flushPromises();

    // Empty src should not create a player
    expect(mockVideoJs).not.toHaveBeenCalled();
  });

  it("does not initialize player with whitespace-only src", async () => {
    render(<VideoPlayer src="   " />);

    await flushPromises();

    // Whitespace-only src should not create a player
    expect(mockVideoJs).not.toHaveBeenCalled();
  });

  it("initializes player with valid src", async () => {
    render(<VideoPlayer src="https://cdn.example.com/v1/index.m3u8" />);

    await flushPromises();

    // Valid src should create player
    expect(mockVideoJs).toHaveBeenCalledTimes(1);
  });
});
