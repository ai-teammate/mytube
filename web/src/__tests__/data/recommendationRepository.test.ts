/**
 * Unit tests for ApiRecommendationRepository
 */
import { ApiRecommendationRepository } from "@/data/videoRepository";

const mockFetch = jest.fn();
global.fetch = mockFetch;

describe("ApiRecommendationRepository", () => {
  const repo = new ApiRecommendationRepository("https://api.example.com");

  beforeEach(() => {
    jest.clearAllMocks();
  });

  it("throws when the API responds with a non-ok status", async () => {
    mockFetch.mockResolvedValue({ status: 500, ok: false });

    await expect(repo.getRecommendations("vid-1")).rejects.toThrow(
      "Failed to fetch recommendations for vid-1: 500"
    );
  });

  it("returns an empty array when recommendations array is missing", async () => {
    mockFetch.mockResolvedValue({
      status: 200,
      ok: true,
      json: async () => ({}),
    });

    const result = await repo.getRecommendations("vid-1");

    expect(result).toEqual([]);
  });

  it("returns an empty array when recommendations is an empty array", async () => {
    mockFetch.mockResolvedValue({
      status: 200,
      ok: true,
      json: async () => ({ recommendations: [] }),
    });

    const result = await repo.getRecommendations("vid-1");

    expect(result).toEqual([]);
  });

  it("maps snake_case API response to camelCase VideoCardItem", async () => {
    const apiResponse = {
      recommendations: [
        {
          id: "vid-2",
          title: "Related Video",
          thumbnail_url: "https://cdn.example.com/thumb.jpg",
          view_count: 500,
          uploader_username: "bob",
          created_at: "2024-01-15T10:00:00Z",
        },
      ],
    };
    mockFetch.mockResolvedValue({
      status: 200,
      ok: true,
      json: async () => apiResponse,
    });

    const result = await repo.getRecommendations("vid-1");

    expect(result).toHaveLength(1);
    expect(result[0].id).toBe("vid-2");
    expect(result[0].title).toBe("Related Video");
    expect(result[0].thumbnailUrl).toBe("https://cdn.example.com/thumb.jpg");
    expect(result[0].viewCount).toBe(500);
    expect(result[0].uploaderUsername).toBe("bob");
    expect(result[0].createdAt).toBe("2024-01-15T10:00:00Z");
  });

  it("maps null thumbnail_url to null", async () => {
    mockFetch.mockResolvedValue({
      status: 200,
      ok: true,
      json: async () => ({
        recommendations: [
          {
            id: "vid-2",
            title: "No Thumb",
            thumbnail_url: null,
            view_count: 0,
            uploader_username: "alice",
            created_at: "2024-01-01T00:00:00Z",
          },
        ],
      }),
    });

    const result = await repo.getRecommendations("vid-1");

    expect(result[0].thumbnailUrl).toBeNull();
  });

  it("maps multiple recommendations correctly", async () => {
    const apiResponse = {
      recommendations: [
        { id: "a", title: "A", thumbnail_url: null, view_count: 10, uploader_username: "u1", created_at: "2024-01-01T00:00:00Z" },
        { id: "b", title: "B", thumbnail_url: null, view_count: 20, uploader_username: "u2", created_at: "2024-01-02T00:00:00Z" },
        { id: "c", title: "C", thumbnail_url: null, view_count: 30, uploader_username: "u3", created_at: "2024-01-03T00:00:00Z" },
      ],
    };
    mockFetch.mockResolvedValue({
      status: 200,
      ok: true,
      json: async () => apiResponse,
    });

    const result = await repo.getRecommendations("vid-1");

    expect(result).toHaveLength(3);
    expect(result.map((v) => v.id)).toEqual(["a", "b", "c"]);
  });

  it("URL-encodes the video ID in the request URL", async () => {
    mockFetch.mockResolvedValue({
      status: 200,
      ok: true,
      json: async () => ({ recommendations: [] }),
    });

    await repo.getRecommendations("video id with spaces");

    expect(mockFetch).toHaveBeenCalledWith(
      "https://api.example.com/api/videos/video%20id%20with%20spaces/recommendations"
    );
  });

  it("uses the default API_URL when no base URL is passed", async () => {
    const defaultRepo = new ApiRecommendationRepository();
    mockFetch.mockResolvedValue({
      status: 200,
      ok: true,
      json: async () => ({ recommendations: [] }),
    });

    await defaultRepo.getRecommendations("test-id");

    expect(mockFetch).toHaveBeenCalledWith(
      "/api/videos/test-id/recommendations"
    );
  });
});
