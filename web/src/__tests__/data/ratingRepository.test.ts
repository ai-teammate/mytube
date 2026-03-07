/**
 * Unit tests for src/data/ratingRepository.ts
 */
import { ApiRatingRepository } from "@/data/ratingRepository";

const mockFetch = jest.fn();
global.fetch = mockFetch;

describe("ApiRatingRepository", () => {
  const repo = new ApiRatingRepository("https://api.example.com");

  beforeEach(() => {
    jest.clearAllMocks();
  });

  // ─── getSummary ──────────────────────────────────────────────────────────────

  it("getSummary: returns mapped summary on success", async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({
        average_rating: 4.2,
        rating_count: 10,
        my_rating: 4,
      }),
    });

    const result = await repo.getSummary("vid-1", null);

    expect(result.averageRating).toBe(4.2);
    expect(result.ratingCount).toBe(10);
    expect(result.myRating).toBe(4);
    expect(mockFetch).toHaveBeenCalledWith(
      "https://api.example.com/api/videos/vid-1/rating",
      expect.objectContaining({})
    );
  });

  it("getSummary: my_rating null maps to null", async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({
        average_rating: 3.0,
        rating_count: 2,
        my_rating: null,
      }),
    });

    const result = await repo.getSummary("vid-1", null);
    expect(result.myRating).toBeNull();
  });

  it("getSummary: throws on non-OK response", async () => {
    mockFetch.mockResolvedValue({ ok: false, status: 500 });

    await expect(repo.getSummary("vid-1", null)).rejects.toThrow(
      "Failed to fetch rating for vid-1: 500"
    );
  });

  it("getSummary: includes Authorization header when token provided", async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ average_rating: 0, rating_count: 0, my_rating: null }),
    });

    await repo.getSummary("vid-1", "my-token");

    expect(mockFetch).toHaveBeenCalledWith(
      expect.any(String),
      expect.objectContaining({
        headers: expect.objectContaining({ Authorization: "Bearer my-token" }),
      })
    );
  });

  it("getSummary: no Authorization header when token is null", async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ average_rating: 0, rating_count: 0, my_rating: null }),
    });

    await repo.getSummary("vid-1", null);

    const [, options] = mockFetch.mock.calls[0];
    expect(options?.headers?.Authorization).toBeUndefined();
  });

  it("getSummary: URL-encodes video ID", async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ average_rating: 0, rating_count: 0, my_rating: null }),
    });

    await repo.getSummary("video id with spaces", null);

    expect(mockFetch).toHaveBeenCalledWith(
      "https://api.example.com/api/videos/video%20id%20with%20spaces/rating",
      expect.anything()
    );
  });

  it("getSummary: uses default API_URL when no base URL provided", async () => {
    const defaultRepo = new ApiRatingRepository();
    mockFetch.mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ average_rating: 0, rating_count: 0, my_rating: null }),
    });

    await defaultRepo.getSummary("vid-1", null);

    expect(mockFetch).toHaveBeenCalledWith(
      "/api/videos/vid-1/rating",
      expect.anything()
    );
  });

  // ─── submitRating ────────────────────────────────────────────────────────────

  it("submitRating: sends POST with stars and returns mapped summary", async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({
        average_rating: 4.5,
        rating_count: 6,
        my_rating: 5,
      }),
    });

    const result = await repo.submitRating("vid-1", 5, "my-token");

    expect(result.averageRating).toBe(4.5);
    expect(result.ratingCount).toBe(6);
    expect(result.myRating).toBe(5);

    expect(mockFetch).toHaveBeenCalledWith(
      "https://api.example.com/api/videos/vid-1/rating",
      expect.objectContaining({
        method: "POST",
        headers: expect.objectContaining({
          Authorization: "Bearer my-token",
          "Content-Type": "application/json",
        }),
        body: JSON.stringify({ stars: 5 }),
      })
    );
  });

  it("submitRating: throws on non-OK response", async () => {
    mockFetch.mockResolvedValue({ ok: false, status: 422 });

    await expect(repo.submitRating("vid-1", 6, "token")).rejects.toThrow(
      "Failed to submit rating for vid-1: 422"
    );
  });

  it("submitRating: URL-encodes video ID", async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ average_rating: 0, rating_count: 0, my_rating: null }),
    });

    await repo.submitRating("video with spaces", 3, "token");

    expect(mockFetch).toHaveBeenCalledWith(
      "https://api.example.com/api/videos/video%20with%20spaces/rating",
      expect.anything()
    );
  });
});
