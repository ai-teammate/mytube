/**
 * Unit tests for src/data/commentRepository.ts
 */
import { ApiCommentRepository } from "@/data/commentRepository";

const mockFetch = jest.fn();
global.fetch = mockFetch;

const mockComment = {
  id: "c-1",
  body: "Great video!",
  author: {
    username: "alice",
    avatar_url: "https://example.com/avatar.png",
  },
  created_at: "2024-01-15T10:00:00Z",
};

describe("ApiCommentRepository", () => {
  const repo = new ApiCommentRepository("https://api.example.com");

  beforeEach(() => {
    jest.clearAllMocks();
  });

  // ─── listByVideoID ────────────────────────────────────────────────────────────

  it("listByVideoID: returns mapped comments on success", async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => [mockComment],
    });

    const result = await repo.listByVideoID("vid-1");

    expect(result).toHaveLength(1);
    expect(result[0].id).toBe("c-1");
    expect(result[0].body).toBe("Great video!");
    expect(result[0].author.username).toBe("alice");
    expect(result[0].author.avatarUrl).toBe("https://example.com/avatar.png");
    expect(result[0].createdAt).toBe("2024-01-15T10:00:00Z");
  });

  it("listByVideoID: maps null avatar_url to null", async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => [
        { ...mockComment, author: { username: "bob", avatar_url: null } },
      ],
    });

    const result = await repo.listByVideoID("vid-1");
    expect(result[0].author.avatarUrl).toBeNull();
  });

  it("listByVideoID: returns empty array when API returns empty", async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => [],
    });

    const result = await repo.listByVideoID("vid-1");
    expect(result).toHaveLength(0);
  });

  it("listByVideoID: throws on non-OK response", async () => {
    mockFetch.mockResolvedValue({ ok: false, status: 500 });

    await expect(repo.listByVideoID("vid-1")).rejects.toThrow(
      "Failed to fetch comments for vid-1: 500"
    );
  });

  it("listByVideoID: URL-encodes video ID", async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => [],
    });

    await repo.listByVideoID("video id with spaces");

    expect(mockFetch).toHaveBeenCalledWith(
      "https://api.example.com/api/videos/video%20id%20with%20spaces/comments"
    );
  });

  it("listByVideoID: uses default API_URL when no base URL provided", async () => {
    const defaultRepo = new ApiCommentRepository();
    mockFetch.mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => [],
    });

    await defaultRepo.listByVideoID("vid-1");

    expect(mockFetch).toHaveBeenCalledWith("/api/videos/vid-1/comments");
  });

  // ─── create ───────────────────────────────────────────────────────────────────

  it("create: sends POST and returns mapped comment", async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      status: 201,
      json: async () => mockComment,
    });

    const result = await repo.create("vid-1", "Great video!", "my-token");

    expect(result.id).toBe("c-1");
    expect(result.body).toBe("Great video!");
    expect(result.author.username).toBe("alice");

    expect(mockFetch).toHaveBeenCalledWith(
      "https://api.example.com/api/videos/vid-1/comments",
      expect.objectContaining({
        method: "POST",
        headers: expect.objectContaining({
          Authorization: "Bearer my-token",
          "Content-Type": "application/json",
        }),
        body: JSON.stringify({ body: "Great video!" }),
      })
    );
  });

  it("create: throws on non-OK response", async () => {
    mockFetch.mockResolvedValue({ ok: false, status: 422 });

    await expect(repo.create("vid-1", "body", "token")).rejects.toThrow(
      "Failed to create comment for vid-1: 422"
    );
  });

  it("create: URL-encodes video ID", async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      status: 201,
      json: async () => mockComment,
    });

    await repo.create("video with spaces", "body", "token");

    expect(mockFetch).toHaveBeenCalledWith(
      "https://api.example.com/api/videos/video%20with%20spaces/comments",
      expect.anything()
    );
  });

  // ─── deleteComment ─────────────────────────────────────────────────────────

  it("deleteComment: sends DELETE with auth header", async () => {
    mockFetch.mockResolvedValue({ ok: true, status: 204 });

    await repo.deleteComment("comment-1", "my-token");

    expect(mockFetch).toHaveBeenCalledWith(
      "https://api.example.com/api/comments/comment-1",
      expect.objectContaining({
        method: "DELETE",
        headers: expect.objectContaining({
          Authorization: "Bearer my-token",
        }),
      })
    );
  });

  it("deleteComment: throws on non-OK response", async () => {
    mockFetch.mockResolvedValue({ ok: false, status: 404 });

    await expect(repo.deleteComment("comment-1", "token")).rejects.toThrow(
      "Failed to delete comment comment-1: 404"
    );
  });

  it("deleteComment: URL-encodes comment ID", async () => {
    mockFetch.mockResolvedValue({ ok: true, status: 204 });

    await repo.deleteComment("comment id with spaces", "token");

    expect(mockFetch).toHaveBeenCalledWith(
      "https://api.example.com/api/comments/comment%20id%20with%20spaces",
      expect.anything()
    );
  });

  it("deleteComment: resolves without error on 204", async () => {
    mockFetch.mockResolvedValue({ ok: true, status: 204 });

    await expect(repo.deleteComment("c-1", "token")).resolves.toBeUndefined();
  });
});
