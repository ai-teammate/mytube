/**
 * Unit tests for src/data/dashboardRepository.ts
 */
import {
  ApiDashboardVideoRepository,
  ApiVideoManagementRepository,
} from "@/data/dashboardRepository";

const mockFetch = jest.fn();
global.fetch = mockFetch;

describe("ApiDashboardVideoRepository", () => {
  const repo = new ApiDashboardVideoRepository("https://api.example.com");

  beforeEach(() => {
    jest.clearAllMocks();
  });

  it("calls GET /api/me/videos with Authorization header", async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      json: async () => [],
    });

    await repo.listMyVideos("test-token");

    expect(mockFetch).toHaveBeenCalledTimes(1);
    const [url, options] = mockFetch.mock.calls[0];
    expect(url).toBe("https://api.example.com/api/me/videos");
    expect(options.headers["Authorization"]).toBe("Bearer test-token");
  });

  it("maps snake_case response fields to camelCase domain model", async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      json: async () => [
        {
          id: "vid-1",
          title: "Test Video",
          status: "ready",
          thumbnail_url: "https://cdn.example.com/thumb.jpg",
          view_count: 42,
          created_at: "2024-01-15T10:00:00Z",
          description: "A test description",
          category_id: 2,
          tags: ["go", "tutorial"],
        },
      ],
    });

    const videos = await repo.listMyVideos("token");

    expect(videos).toHaveLength(1);
    expect(videos[0]).toEqual({
      id: "vid-1",
      title: "Test Video",
      status: "ready",
      thumbnailUrl: "https://cdn.example.com/thumb.jpg",
      viewCount: 42,
      createdAt: "2024-01-15T10:00:00Z",
      description: "A test description",
      categoryId: 2,
      tags: ["go", "tutorial"],
    });
  });

  it("returns empty array when API returns empty list", async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      json: async () => [],
    });

    const videos = await repo.listMyVideos("token");
    expect(videos).toEqual([]);
  });

  it("maps null thumbnail_url correctly", async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      json: async () => [
        {
          id: "vid-2",
          title: "No Thumb",
          status: "pending",
          thumbnail_url: null,
          view_count: 0,
          created_at: "2024-01-15T10:00:00Z",
          description: null,
          category_id: null,
          tags: [],
        },
      ],
    });

    const videos = await repo.listMyVideos("token");
    expect(videos[0].thumbnailUrl).toBeNull();
  });

  it("throws with API error message on non-ok response", async () => {
    mockFetch.mockResolvedValue({
      ok: false,
      status: 401,
      json: async () => ({ error: "unauthorized" }),
    });

    await expect(repo.listMyVideos("bad-token")).rejects.toThrow("unauthorized");
  });

  it("throws fallback error message when response body has no error field", async () => {
    mockFetch.mockResolvedValue({
      ok: false,
      status: 500,
      json: async () => ({}),
    });

    await expect(repo.listMyVideos("token")).rejects.toThrow(
      "Failed to fetch videos: 500"
    );
  });

  it("uses default API_URL when no base URL passed to constructor", async () => {
    const defaultRepo = new ApiDashboardVideoRepository();
    mockFetch.mockResolvedValue({ ok: true, json: async () => [] });

    await defaultRepo.listMyVideos("token");

    const [url] = mockFetch.mock.calls[0];
    expect(url).toBe("/api/me/videos");
  });
});

describe("ApiVideoManagementRepository", () => {
  const repo = new ApiVideoManagementRepository("https://api.example.com");

  beforeEach(() => {
    jest.clearAllMocks();
  });

  // ─── updateVideo ────────────────────────────────────────────────────────────

  it("calls PUT /api/videos/:id with correct headers and body", async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      json: async () => ({
        id: "vid-1",
        title: "New Title",
        description: "New desc",
        status: "ready",
        thumbnail_url: null,
        view_count: 10,
        tags: ["go"],
        uploader: { username: "alice", avatar_url: null },
      }),
    });

    await repo.updateVideo(
      "vid-1",
      {
        title: "New Title",
        description: "New desc",
        categoryId: 2,
        tags: ["go"],
      },
      "test-token"
    );

    expect(mockFetch).toHaveBeenCalledTimes(1);
    const [url, options] = mockFetch.mock.calls[0];
    expect(url).toBe("https://api.example.com/api/videos/vid-1");
    expect(options.method).toBe("PUT");
    expect(options.headers["Authorization"]).toBe("Bearer test-token");
    expect(options.headers["Content-Type"]).toBe("application/json");

    const body = JSON.parse(options.body);
    expect(body.title).toBe("New Title");
    expect(body.description).toBe("New desc");
    expect(body.category_id).toBe(2);
    expect(body.tags).toEqual(["go"]);
  });

  it("maps PUT response to UpdatedVideo domain type", async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      json: async () => ({
        id: "vid-1",
        title: "Updated Title",
        description: "Updated desc",
        status: "ready",
        thumbnail_url: "https://cdn.example.com/thumb.jpg",
        view_count: 5,
        tags: ["go", "tutorial"],
        uploader: { username: "alice", avatar_url: "https://example.com/avatar.png" },
      }),
    });

    const result = await repo.updateVideo(
      "vid-1",
      { title: "Updated Title", description: "Updated desc", categoryId: null, tags: [] },
      "token"
    );

    expect(result.id).toBe("vid-1");
    expect(result.title).toBe("Updated Title");
    expect(result.description).toBe("Updated desc");
    expect(result.thumbnailUrl).toBe("https://cdn.example.com/thumb.jpg");
    expect(result.tags).toEqual(["go", "tutorial"]);
    expect(result.uploader.username).toBe("alice");
    expect(result.uploader.avatarUrl).toBe("https://example.com/avatar.png");
  });

  it("sends null category_id when categoryId is null", async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      json: async () => ({
        id: "vid-1", title: "T", description: null, status: "ready",
        thumbnail_url: null, view_count: 0, tags: [],
        uploader: { username: "alice", avatar_url: null },
      }),
    });

    await repo.updateVideo("vid-1", { title: "T", description: "", categoryId: null, tags: [] }, "token");

    const body = JSON.parse(mockFetch.mock.calls[0][1].body);
    expect(body.category_id).toBeNull();
  });

  it("throws with API error message on PUT failure", async () => {
    mockFetch.mockResolvedValue({
      ok: false,
      status: 403,
      json: async () => ({ error: "forbidden" }),
    });

    await expect(
      repo.updateVideo("vid-1", { title: "T", description: "", categoryId: null, tags: [] }, "token")
    ).rejects.toThrow("forbidden");
  });

  it("throws fallback error when PUT response has no error field", async () => {
    mockFetch.mockResolvedValue({
      ok: false,
      status: 500,
      json: async () => ({}),
    });

    await expect(
      repo.updateVideo("vid-1", { title: "T", description: "", categoryId: null, tags: [] }, "token")
    ).rejects.toThrow("Failed to update video: 500");
  });

  // ─── deleteVideo ────────────────────────────────────────────────────────────

  it("calls DELETE /api/videos/:id with correct headers", async () => {
    mockFetch.mockResolvedValue({ ok: true, json: async () => ({}) });

    await repo.deleteVideo("vid-1", "test-token");

    expect(mockFetch).toHaveBeenCalledTimes(1);
    const [url, options] = mockFetch.mock.calls[0];
    expect(url).toBe("https://api.example.com/api/videos/vid-1");
    expect(options.method).toBe("DELETE");
    expect(options.headers["Authorization"]).toBe("Bearer test-token");
  });

  it("resolves without value on successful DELETE", async () => {
    // 204 No Content - no body
    mockFetch.mockResolvedValue({ ok: true, json: async () => ({}) });

    await expect(repo.deleteVideo("vid-1", "token")).resolves.toBeUndefined();
  });

  it("throws with API error message on DELETE failure", async () => {
    mockFetch.mockResolvedValue({
      ok: false,
      status: 403,
      json: async () => ({ error: "forbidden" }),
    });

    await expect(repo.deleteVideo("vid-1", "token")).rejects.toThrow("forbidden");
  });

  it("throws fallback error when DELETE response has no error field", async () => {
    mockFetch.mockResolvedValue({
      ok: false,
      status: 500,
      json: async () => ({}),
    });

    await expect(repo.deleteVideo("vid-1", "token")).rejects.toThrow(
      "Failed to delete video: 500"
    );
  });

  it("uses default API_URL when no base URL passed to constructor", async () => {
    const defaultRepo = new ApiVideoManagementRepository();
    mockFetch.mockResolvedValue({ ok: true, json: async () => ({}) });

    await defaultRepo.deleteVideo("vid-1", "token");

    const [url] = mockFetch.mock.calls[0];
    expect(url).toBe("/api/videos/vid-1");
  });
});
