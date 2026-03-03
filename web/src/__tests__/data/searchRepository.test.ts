/**
 * Unit tests for src/data/searchRepository.ts
 */
import {
  ApiSearchRepository,
  ApiDiscoveryRepository,
  ApiCategoryRepository,
} from "@/data/searchRepository";

const mockFetch = jest.fn();
global.fetch = mockFetch;

function mockOk(body: unknown) {
  return {
    status: 200,
    ok: true,
    json: async () => body,
  };
}

function mockError(status: number) {
  return { status, ok: false };
}

beforeEach(() => {
  jest.clearAllMocks();
});

// ─── ApiSearchRepository ───────────────────────────────────────────────────────

describe("ApiSearchRepository", () => {
  const repo = new ApiSearchRepository("https://api.example.com");

  it("calls /api/search with query parameter", async () => {
    mockFetch.mockResolvedValue(mockOk([]));
    await repo.search("go");
    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining("/api/search?")
    );
    const url = mockFetch.mock.calls[0][0] as string;
    expect(url).toContain("q=go");
  });

  it("includes category_id when provided", async () => {
    mockFetch.mockResolvedValue(mockOk([]));
    await repo.search("music", 3);
    const url = mockFetch.mock.calls[0][0] as string;
    expect(url).toContain("category_id=3");
  });

  it("includes limit and offset", async () => {
    mockFetch.mockResolvedValue(mockOk([]));
    await repo.search("test", undefined, 10, 20);
    const url = mockFetch.mock.calls[0][0] as string;
    expect(url).toContain("limit=10");
    expect(url).toContain("offset=20");
  });

  it("returns mapped VideoCardItems on success", async () => {
    const apiResponse = [
      {
        id: "vid-1",
        title: "Go Tutorial",
        thumbnail_url: "https://cdn.example.com/thumb.jpg",
        view_count: 100,
        uploader_username: "alice",
        created_at: "2024-01-15T10:00:00Z",
      },
    ];
    mockFetch.mockResolvedValue(mockOk(apiResponse));

    const result = await repo.search("go");

    expect(result).toHaveLength(1);
    expect(result[0].id).toBe("vid-1");
    expect(result[0].title).toBe("Go Tutorial");
    expect(result[0].thumbnailUrl).toBe("https://cdn.example.com/thumb.jpg");
    expect(result[0].viewCount).toBe(100);
    expect(result[0].uploaderUsername).toBe("alice");
    expect(result[0].createdAt).toBe("2024-01-15T10:00:00Z");
  });

  it("maps null thumbnail_url to null", async () => {
    mockFetch.mockResolvedValue(
      mockOk([
        {
          id: "v1",
          title: "No Thumb",
          thumbnail_url: null,
          view_count: 0,
          uploader_username: "bob",
          created_at: "2024-01-01T00:00:00Z",
        },
      ])
    );

    const result = await repo.search("test");
    expect(result[0].thumbnailUrl).toBeNull();
  });

  it("returns empty array when API returns empty array", async () => {
    mockFetch.mockResolvedValue(mockOk([]));
    const result = await repo.search("nothing");
    expect(result).toHaveLength(0);
  });

  it("throws on non-ok response", async () => {
    mockFetch.mockResolvedValue(mockError(500));
    await expect(repo.search("test")).rejects.toThrow("Search failed: 500");
  });

  it("does not include category_id param when undefined", async () => {
    mockFetch.mockResolvedValue(mockOk([]));
    await repo.search("go", undefined);
    const url = mockFetch.mock.calls[0][0] as string;
    expect(url).not.toContain("category_id");
  });
});

// ─── ApiDiscoveryRepository ────────────────────────────────────────────────────

describe("ApiDiscoveryRepository", () => {
  const repo = new ApiDiscoveryRepository("https://api.example.com");

  it("getRecent calls /api/videos/recent", async () => {
    mockFetch.mockResolvedValue(mockOk([]));
    await repo.getRecent();
    expect(mockFetch).toHaveBeenCalledWith(
      "https://api.example.com/api/videos/recent?limit=20"
    );
  });

  it("getRecent uses custom limit", async () => {
    mockFetch.mockResolvedValue(mockOk([]));
    await repo.getRecent(5);
    expect(mockFetch).toHaveBeenCalledWith(
      "https://api.example.com/api/videos/recent?limit=5"
    );
  });

  it("getRecent returns mapped videos", async () => {
    mockFetch.mockResolvedValue(
      mockOk([
        {
          id: "r1",
          title: "Recent Video",
          thumbnail_url: null,
          view_count: 50,
          uploader_username: "carol",
          created_at: "2024-02-01T00:00:00Z",
        },
      ])
    );

    const result = await repo.getRecent();
    expect(result).toHaveLength(1);
    expect(result[0].title).toBe("Recent Video");
  });

  it("getRecent throws on error", async () => {
    mockFetch.mockResolvedValue(mockError(500));
    await expect(repo.getRecent()).rejects.toThrow(
      "Failed to fetch recent videos: 500"
    );
  });

  it("getPopular calls /api/videos/popular", async () => {
    mockFetch.mockResolvedValue(mockOk([]));
    await repo.getPopular();
    expect(mockFetch).toHaveBeenCalledWith(
      "https://api.example.com/api/videos/popular?limit=20"
    );
  });

  it("getPopular uses custom limit", async () => {
    mockFetch.mockResolvedValue(mockOk([]));
    await repo.getPopular(10);
    expect(mockFetch).toHaveBeenCalledWith(
      "https://api.example.com/api/videos/popular?limit=10"
    );
  });

  it("getPopular returns mapped videos", async () => {
    mockFetch.mockResolvedValue(
      mockOk([
        {
          id: "p1",
          title: "Popular Video",
          thumbnail_url: "https://cdn.example.com/pop.jpg",
          view_count: 9999,
          uploader_username: "dave",
          created_at: "2024-01-01T00:00:00Z",
        },
      ])
    );

    const result = await repo.getPopular();
    expect(result).toHaveLength(1);
    expect(result[0].viewCount).toBe(9999);
  });

  it("getPopular throws on error", async () => {
    mockFetch.mockResolvedValue(mockError(503));
    await expect(repo.getPopular()).rejects.toThrow(
      "Failed to fetch popular videos: 503"
    );
  });
});

// ─── ApiCategoryRepository ─────────────────────────────────────────────────────

describe("ApiCategoryRepository", () => {
  const repo = new ApiCategoryRepository("https://api.example.com");

  it("getAll calls /api/categories", async () => {
    mockFetch.mockResolvedValue(mockOk([]));
    await repo.getAll();
    expect(mockFetch).toHaveBeenCalledWith(
      "https://api.example.com/api/categories"
    );
  });

  it("getAll returns mapped categories", async () => {
    mockFetch.mockResolvedValue(
      mockOk([
        { id: 1, name: "Education" },
        { id: 2, name: "Gaming" },
      ])
    );

    const result = await repo.getAll();
    expect(result).toHaveLength(2);
    expect(result[0].id).toBe(1);
    expect(result[0].name).toBe("Education");
    expect(result[1].name).toBe("Gaming");
  });

  it("getAll returns empty array on empty response", async () => {
    mockFetch.mockResolvedValue(mockOk([]));
    const result = await repo.getAll();
    expect(result).toHaveLength(0);
  });

  it("getAll throws on error", async () => {
    mockFetch.mockResolvedValue(mockError(500));
    await expect(repo.getAll()).rejects.toThrow("Failed to fetch categories: 500");
  });

  it("getVideosByCategory calls /api/videos with category_id", async () => {
    mockFetch.mockResolvedValue(mockOk([]));
    await repo.getVideosByCategory(3);
    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining("category_id=3")
    );
  });

  it("getVideosByCategory includes limit and offset", async () => {
    mockFetch.mockResolvedValue(mockOk([]));
    await repo.getVideosByCategory(2, 10, 5);
    const url = mockFetch.mock.calls[0][0] as string;
    expect(url).toContain("category_id=2");
    expect(url).toContain("limit=10");
    expect(url).toContain("offset=5");
  });

  it("getVideosByCategory returns mapped videos", async () => {
    mockFetch.mockResolvedValue(
      mockOk([
        {
          id: "c1",
          title: "Cat Video",
          thumbnail_url: null,
          view_count: 5,
          uploader_username: "eve",
          created_at: "2024-03-01T00:00:00Z",
        },
      ])
    );

    const result = await repo.getVideosByCategory(1);
    expect(result).toHaveLength(1);
    expect(result[0].title).toBe("Cat Video");
    expect(result[0].uploaderUsername).toBe("eve");
  });

  it("getVideosByCategory throws on error", async () => {
    mockFetch.mockResolvedValue(mockError(404));
    await expect(repo.getVideosByCategory(99)).rejects.toThrow(
      "Failed to fetch videos for category 99: 404"
    );
  });
});
