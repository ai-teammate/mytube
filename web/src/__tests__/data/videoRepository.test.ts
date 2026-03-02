/**
 * Unit tests for src/data/videoRepository.ts
 */
import { ApiVideoRepository } from "@/data/videoRepository";

const mockFetch = jest.fn();
global.fetch = mockFetch;

describe("ApiVideoRepository", () => {
  const repo = new ApiVideoRepository("https://api.example.com");

  beforeEach(() => {
    jest.clearAllMocks();
  });

  it("returns null when the API responds with 404", async () => {
    mockFetch.mockResolvedValue({ status: 404, ok: false });

    const result = await repo.getByID("nonexistent-id");

    expect(result).toBeNull();
    expect(mockFetch).toHaveBeenCalledWith(
      "https://api.example.com/api/videos/nonexistent-id"
    );
  });

  it("throws when the API responds with a non-404 error", async () => {
    mockFetch.mockResolvedValue({ status: 500, ok: false });

    await expect(repo.getByID("vid-1")).rejects.toThrow(
      "Failed to fetch video vid-1: 500"
    );
  });

  it("returns a mapped video on success", async () => {
    const apiResponse = {
      id: "vid-1",
      title: "Test Video",
      description: "A description",
      hls_manifest_url: "https://cdn.example.com/videos/vid-1/index.m3u8",
      thumbnail_url: "https://cdn.example.com/thumb.jpg",
      view_count: 100,
      created_at: "2024-01-15T10:00:00Z",
      status: "ready",
      uploader: {
        username: "alice",
        avatar_url: "https://example.com/avatar.png",
      },
      tags: ["go", "programming"],
    };
    mockFetch.mockResolvedValue({
      status: 200,
      ok: true,
      json: async () => apiResponse,
    });

    const result = await repo.getByID("vid-1");

    expect(result).not.toBeNull();
    expect(result!.id).toBe("vid-1");
    expect(result!.title).toBe("Test Video");
    expect(result!.description).toBe("A description");
    expect(result!.hlsManifestUrl).toBe(
      "https://cdn.example.com/videos/vid-1/index.m3u8"
    );
    expect(result!.thumbnailUrl).toBe("https://cdn.example.com/thumb.jpg");
    expect(result!.viewCount).toBe(100);
    expect(result!.createdAt).toBe("2024-01-15T10:00:00Z");
    expect(result!.status).toBe("ready");
    expect(result!.uploader.username).toBe("alice");
    expect(result!.uploader.avatarUrl).toBe("https://example.com/avatar.png");
    expect(result!.tags).toEqual(["go", "programming"]);
  });

  it("maps null description to null", async () => {
    mockFetch.mockResolvedValue({
      status: 200,
      ok: true,
      json: async () => ({
        id: "vid-1",
        title: "No Description",
        description: null,
        hls_manifest_url: null,
        thumbnail_url: null,
        view_count: 0,
        created_at: "2024-01-01T00:00:00Z",
        status: "ready",
        uploader: { username: "bob", avatar_url: null },
        tags: [],
      }),
    });

    const result = await repo.getByID("vid-1");

    expect(result!.description).toBeNull();
  });

  it("maps undefined description to null", async () => {
    mockFetch.mockResolvedValue({
      status: 200,
      ok: true,
      json: async () => ({
        id: "vid-1",
        title: "No Description",
        hls_manifest_url: null,
        thumbnail_url: null,
        view_count: 0,
        created_at: "2024-01-01T00:00:00Z",
        status: "ready",
        uploader: { username: "bob", avatar_url: null },
        tags: [],
      }),
    });

    const result = await repo.getByID("vid-1");

    expect(result!.description).toBeNull();
  });

  it("maps null hls_manifest_url to null", async () => {
    mockFetch.mockResolvedValue({
      status: 200,
      ok: true,
      json: async () => ({
        id: "vid-1",
        title: "No HLS",
        description: null,
        hls_manifest_url: null,
        thumbnail_url: null,
        view_count: 0,
        created_at: "2024-01-01T00:00:00Z",
        status: "ready",
        uploader: { username: "bob", avatar_url: null },
        tags: [],
      }),
    });

    const result = await repo.getByID("vid-1");

    expect(result!.hlsManifestUrl).toBeNull();
  });

  it("maps null thumbnail_url to null", async () => {
    mockFetch.mockResolvedValue({
      status: 200,
      ok: true,
      json: async () => ({
        id: "vid-1",
        title: "No Thumb",
        description: null,
        hls_manifest_url: null,
        thumbnail_url: null,
        view_count: 0,
        created_at: "2024-01-01T00:00:00Z",
        status: "ready",
        uploader: { username: "bob", avatar_url: null },
        tags: [],
      }),
    });

    const result = await repo.getByID("vid-1");

    expect(result!.thumbnailUrl).toBeNull();
  });

  it("maps null uploader avatar_url to null", async () => {
    mockFetch.mockResolvedValue({
      status: 200,
      ok: true,
      json: async () => ({
        id: "vid-1",
        title: "No Avatar",
        description: null,
        hls_manifest_url: null,
        thumbnail_url: null,
        view_count: 0,
        created_at: "2024-01-01T00:00:00Z",
        status: "ready",
        uploader: { username: "carol", avatar_url: null },
        tags: [],
      }),
    });

    const result = await repo.getByID("vid-1");

    expect(result!.uploader.avatarUrl).toBeNull();
  });

  it("returns empty tags array when tags is missing", async () => {
    mockFetch.mockResolvedValue({
      status: 200,
      ok: true,
      json: async () => ({
        id: "vid-1",
        title: "No Tags",
        description: null,
        hls_manifest_url: null,
        thumbnail_url: null,
        view_count: 0,
        created_at: "2024-01-01T00:00:00Z",
        status: "ready",
        uploader: { username: "dave", avatar_url: null },
      }),
    });

    const result = await repo.getByID("vid-1");

    expect(result!.tags).toHaveLength(0);
  });

  it("URL-encodes the video ID in the request URL", async () => {
    mockFetch.mockResolvedValue({ status: 404, ok: false });

    await repo.getByID("video id with spaces");

    expect(mockFetch).toHaveBeenCalledWith(
      "https://api.example.com/api/videos/video%20id%20with%20spaces"
    );
  });

  it("uses the default API_URL when no base URL is passed to constructor", async () => {
    const defaultRepo = new ApiVideoRepository();
    mockFetch.mockResolvedValue({ status: 404, ok: false });

    await defaultRepo.getByID("test-id");

    expect(mockFetch).toHaveBeenCalledWith("/api/videos/test-id");
  });
});
