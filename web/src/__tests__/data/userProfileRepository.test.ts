/**
 * Unit tests for src/data/userProfileRepository.ts
 */
import { ApiUserProfileRepository } from "@/data/userProfileRepository";

const mockFetch = jest.fn();
global.fetch = mockFetch;

describe("ApiUserProfileRepository", () => {
  const repo = new ApiUserProfileRepository("https://api.example.com");

  beforeEach(() => {
    jest.clearAllMocks();
  });

  it("returns null when the API responds with 404", async () => {
    mockFetch.mockResolvedValue({ status: 404, ok: false });

    const result = await repo.getByUsername("unknown");

    expect(result).toBeNull();
    expect(mockFetch).toHaveBeenCalledWith(
      "https://api.example.com/api/users/unknown"
    );
  });

  it("throws when the API responds with a non-404 error", async () => {
    mockFetch.mockResolvedValue({ status: 500, ok: false });

    await expect(repo.getByUsername("alice")).rejects.toThrow(
      "Failed to fetch profile for alice: 500"
    );
  });

  it("returns a mapped profile on success", async () => {
    const apiResponse = {
      username: "alice",
      avatar_url: "https://example.com/avatar.png",
      videos: [
        {
          id: "v1",
          title: "Hello World",
          thumbnail_url: "https://example.com/thumb.jpg",
          view_count: 42,
          created_at: "2024-01-15T10:00:00Z",
        },
      ],
    };
    mockFetch.mockResolvedValue({
      status: 200,
      ok: true,
      json: async () => apiResponse,
    });

    const result = await repo.getByUsername("alice");

    expect(result).not.toBeNull();
    expect(result!.username).toBe("alice");
    expect(result!.avatarUrl).toBe("https://example.com/avatar.png");
    expect(result!.videos).toHaveLength(1);
    expect(result!.videos[0].id).toBe("v1");
    expect(result!.videos[0].title).toBe("Hello World");
    expect(result!.videos[0].thumbnailUrl).toBe(
      "https://example.com/thumb.jpg"
    );
    expect(result!.videos[0].viewCount).toBe(42);
    expect(result!.videos[0].createdAt).toBe("2024-01-15T10:00:00Z");
  });

  it("maps null avatar_url to null", async () => {
    mockFetch.mockResolvedValue({
      status: 200,
      ok: true,
      json: async () => ({
        username: "bob",
        avatar_url: null,
        videos: [],
      }),
    });

    const result = await repo.getByUsername("bob");

    expect(result!.avatarUrl).toBeNull();
  });

  it("maps undefined avatar_url to null", async () => {
    mockFetch.mockResolvedValue({
      status: 200,
      ok: true,
      json: async () => ({
        username: "carol",
        videos: [],
      }),
    });

    const result = await repo.getByUsername("carol");

    expect(result!.avatarUrl).toBeNull();
  });

  it("maps null thumbnail_url to null on video", async () => {
    mockFetch.mockResolvedValue({
      status: 200,
      ok: true,
      json: async () => ({
        username: "dave",
        avatar_url: null,
        videos: [
          {
            id: "v2",
            title: "No thumb",
            thumbnail_url: null,
            view_count: 0,
            created_at: "2024-01-01T00:00:00Z",
          },
        ],
      }),
    });

    const result = await repo.getByUsername("dave");

    expect(result!.videos[0].thumbnailUrl).toBeNull();
  });

  it("returns an empty video array when videos field is missing", async () => {
    mockFetch.mockResolvedValue({
      status: 200,
      ok: true,
      json: async () => ({ username: "eve", avatar_url: null }),
    });

    const result = await repo.getByUsername("eve");

    expect(result!.videos).toHaveLength(0);
  });

  it("URL-encodes the username in the request URL", async () => {
    mockFetch.mockResolvedValue({ status: 404, ok: false });

    await repo.getByUsername("alice bob");

    expect(mockFetch).toHaveBeenCalledWith(
      "https://api.example.com/api/users/alice%20bob"
    );
  });

  it("uses the default API_URL when no base URL is passed to constructor", async () => {
    // The constructor defaults to process.env.NEXT_PUBLIC_API_URL ?? "".
    const defaultRepo = new ApiUserProfileRepository();
    mockFetch.mockResolvedValue({ status: 404, ok: false });

    await defaultRepo.getByUsername("test");

    // With no env var set, the URL should start with "/api/users/"
    expect(mockFetch).toHaveBeenCalledWith("/api/users/test");
  });
});
