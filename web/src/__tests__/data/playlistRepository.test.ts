/**
 * Unit tests for src/data/playlistRepository.ts
 */
import { ApiPlaylistRepository } from "@/data/playlistRepository";
import type { PlaylistDetail, PlaylistSummary } from "@/domain/playlist";

const BASE_URL = "https://api.example.com";

function makeRawSummary(overrides: Partial<Record<string, unknown>> = {}) {
  return {
    id: "pl-1",
    title: "My Playlist",
    owner_username: "alice",
    created_at: "2024-01-01T00:00:00Z",
    ...overrides,
  };
}

function makeRawDetail(overrides: Partial<Record<string, unknown>> = {}) {
  return {
    id: "pl-1",
    title: "My Playlist",
    owner_username: "alice",
    videos: [
      {
        id: "v-1",
        title: "Video 1",
        thumbnail_url: "https://cdn.example.com/thumb.jpg",
        position: 1,
      },
    ],
    ...overrides,
  };
}

describe("ApiPlaylistRepository", () => {
  beforeEach(() => jest.resetAllMocks());

  // ─── getByID ────────────────────────────────────────────────────────────────

  it("getByID returns mapped PlaylistDetail on 200", async () => {
    const raw = makeRawDetail();
    global.fetch = jest.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => raw,
    } as Response);

    const repo = new ApiPlaylistRepository(BASE_URL);
    const result = await repo.getByID("pl-1");

    expect(result).not.toBeNull();
    expect(result!.id).toBe("pl-1");
    expect(result!.title).toBe("My Playlist");
    expect(result!.ownerUsername).toBe("alice");
    expect(result!.videos).toHaveLength(1);
    expect(result!.videos[0].thumbnailUrl).toBe("https://cdn.example.com/thumb.jpg");
  });

  it("getByID returns null on 404", async () => {
    global.fetch = jest.fn().mockResolvedValue({
      ok: false,
      status: 404,
    } as Response);

    const repo = new ApiPlaylistRepository(BASE_URL);
    const result = await repo.getByID("missing");
    expect(result).toBeNull();
  });

  it("getByID returns null on 400 (invalid UUID / bad request)", async () => {
    // MYTUBE-604: a malformed playlist ID returns 400 from the API.
    // The repository must treat this as "not found" (null) so the UI
    // displays "Playlist not found." instead of the generic error.
    global.fetch = jest.fn().mockResolvedValue({
      ok: false,
      status: 400,
    } as Response);

    const repo = new ApiPlaylistRepository(BASE_URL);
    const result = await repo.getByID("not-a-valid-uuid-123");
    expect(result).toBeNull();
  });

  it("getByID throws on non-404 error", async () => {
    global.fetch = jest.fn().mockResolvedValue({
      ok: false,
      status: 500,
    } as Response);

    const repo = new ApiPlaylistRepository(BASE_URL);
    await expect(repo.getByID("pl-1")).rejects.toThrow("500");
  });

  it("getByID maps videos with null thumbnail", async () => {
    const raw = makeRawDetail({
      videos: [{ id: "v-1", title: "Video 1", thumbnail_url: null, position: 1 }],
    });
    global.fetch = jest.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => raw,
    } as Response);

    const repo = new ApiPlaylistRepository(BASE_URL);
    const result = await repo.getByID("pl-1");
    expect(result!.videos[0].thumbnailUrl).toBeNull();
  });

  // ─── create ─────────────────────────────────────────────────────────────────

  it("create posts title and returns mapped summary", async () => {
    const raw = makeRawSummary({ title: "New Playlist" });
    const mockFetch = jest.fn().mockResolvedValue({
      ok: true,
      status: 201,
      json: async () => raw,
    } as Response);
    global.fetch = mockFetch;

    const repo = new ApiPlaylistRepository(BASE_URL);
    const result = await repo.create("New Playlist", "token-123");

    expect(mockFetch).toHaveBeenCalledWith(
      `${BASE_URL}/api/playlists`,
      expect.objectContaining({
        method: "POST",
        headers: expect.objectContaining({
          Authorization: "Bearer token-123",
        }),
      })
    );
    expect(result.title).toBe("New Playlist");
    expect(result.ownerUsername).toBe("alice");
  });

  it("create throws on error", async () => {
    global.fetch = jest.fn().mockResolvedValue({
      ok: false,
      status: 422,
    } as Response);

    const repo = new ApiPlaylistRepository(BASE_URL);
    await expect(repo.create("", "token")).rejects.toThrow("422");
  });

  // ─── listMine ───────────────────────────────────────────────────────────────

  it("listMine fetches with auth header and returns list", async () => {
    const mockFetch = jest.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => [makeRawSummary(), makeRawSummary({ id: "pl-2", title: "Second" })],
    } as Response);
    global.fetch = mockFetch;

    const repo = new ApiPlaylistRepository(BASE_URL);
    const result = await repo.listMine("my-token");

    expect(mockFetch).toHaveBeenCalledWith(
      `${BASE_URL}/api/me/playlists`,
      expect.objectContaining({
        headers: expect.objectContaining({ Authorization: "Bearer my-token" }),
      })
    );
    expect(result).toHaveLength(2);
  });

  it("listMine throws on error", async () => {
    global.fetch = jest.fn().mockResolvedValue({ ok: false, status: 401 } as Response);
    const repo = new ApiPlaylistRepository(BASE_URL);
    await expect(repo.listMine("bad-token")).rejects.toThrow("401");
  });

  // ─── listByUsername ──────────────────────────────────────────────────────────

  it("listByUsername fetches correct URL and returns list", async () => {
    const mockFetch = jest.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => [makeRawSummary()],
    } as Response);
    global.fetch = mockFetch;

    const repo = new ApiPlaylistRepository(BASE_URL);
    const result = await repo.listByUsername("alice");

    expect(mockFetch).toHaveBeenCalledWith(
      `${BASE_URL}/api/users/alice/playlists`
    );
    expect(result).toHaveLength(1);
  });

  it("listByUsername throws on error", async () => {
    global.fetch = jest.fn().mockResolvedValue({ ok: false, status: 404 } as Response);
    const repo = new ApiPlaylistRepository(BASE_URL);
    await expect(repo.listByUsername("nobody")).rejects.toThrow("404");
  });

  // ─── updateTitle ────────────────────────────────────────────────────────────

  it("updateTitle sends PUT and returns updated summary", async () => {
    const raw = makeRawSummary({ title: "Renamed" });
    const mockFetch = jest.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => raw,
    } as Response);
    global.fetch = mockFetch;

    const repo = new ApiPlaylistRepository(BASE_URL);
    const result = await repo.updateTitle("pl-1", "Renamed", "token");

    expect(mockFetch).toHaveBeenCalledWith(
      `${BASE_URL}/api/playlists/pl-1`,
      expect.objectContaining({ method: "PUT" })
    );
    expect(result.title).toBe("Renamed");
  });

  it("updateTitle throws on error", async () => {
    global.fetch = jest.fn().mockResolvedValue({ ok: false, status: 403 } as Response);
    const repo = new ApiPlaylistRepository(BASE_URL);
    await expect(repo.updateTitle("pl-1", "New", "token")).rejects.toThrow("403");
  });

  // ─── deletePlaylist ──────────────────────────────────────────────────────────

  it("deletePlaylist sends DELETE and resolves on 204", async () => {
    const mockFetch = jest.fn().mockResolvedValue({
      ok: true,
      status: 204,
    } as Response);
    global.fetch = mockFetch;

    const repo = new ApiPlaylistRepository(BASE_URL);
    await expect(repo.deletePlaylist("pl-1", "token")).resolves.toBeUndefined();

    expect(mockFetch).toHaveBeenCalledWith(
      `${BASE_URL}/api/playlists/pl-1`,
      expect.objectContaining({ method: "DELETE" })
    );
  });

  it("deletePlaylist throws on error", async () => {
    global.fetch = jest.fn().mockResolvedValue({ ok: false, status: 404 } as Response);
    const repo = new ApiPlaylistRepository(BASE_URL);
    await expect(repo.deletePlaylist("pl-1", "token")).rejects.toThrow("404");
  });

  // ─── addVideo ───────────────────────────────────────────────────────────────

  it("addVideo sends POST with video_id and resolves", async () => {
    const mockFetch = jest.fn().mockResolvedValue({
      ok: true,
      status: 204,
    } as Response);
    global.fetch = mockFetch;

    const repo = new ApiPlaylistRepository(BASE_URL);
    await expect(repo.addVideo("pl-1", "vid-1", "token")).resolves.toBeUndefined();

    expect(mockFetch).toHaveBeenCalledWith(
      `${BASE_URL}/api/playlists/pl-1/videos`,
      expect.objectContaining({ method: "POST" })
    );
    const body = JSON.parse(mockFetch.mock.calls[0][1].body);
    expect(body.video_id).toBe("vid-1");
  });

  it("addVideo throws on error", async () => {
    global.fetch = jest.fn().mockResolvedValue({ ok: false, status: 403 } as Response);
    const repo = new ApiPlaylistRepository(BASE_URL);
    await expect(repo.addVideo("pl-1", "vid-1", "token")).rejects.toThrow("403");
  });

  // ─── removeVideo ─────────────────────────────────────────────────────────────

  it("removeVideo sends DELETE with correct URL and resolves", async () => {
    const mockFetch = jest.fn().mockResolvedValue({
      ok: true,
      status: 204,
    } as Response);
    global.fetch = mockFetch;

    const repo = new ApiPlaylistRepository(BASE_URL);
    await expect(repo.removeVideo("pl-1", "vid-1", "token")).resolves.toBeUndefined();

    expect(mockFetch).toHaveBeenCalledWith(
      `${BASE_URL}/api/playlists/pl-1/videos/vid-1`,
      expect.objectContaining({ method: "DELETE" })
    );
  });

  it("removeVideo throws on error", async () => {
    global.fetch = jest.fn().mockResolvedValue({ ok: false, status: 404 } as Response);
    const repo = new ApiPlaylistRepository(BASE_URL);
    await expect(repo.removeVideo("pl-1", "vid-1", "token")).rejects.toThrow("404");
  });
});
