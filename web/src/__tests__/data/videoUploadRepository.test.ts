/**
 * Unit tests for src/data/videoUploadRepository.ts
 */
import { ApiVideoUploadRepository } from "@/data/videoUploadRepository";

const mockFetch = jest.fn();
global.fetch = mockFetch;

describe("ApiVideoUploadRepository", () => {
  const repo = new ApiVideoUploadRepository("https://api.example.com");

  const mockFile = new File(["video content"], "test.mp4", {
    type: "video/mp4",
  });

  beforeEach(() => {
    jest.clearAllMocks();
  });

  it("calls POST /api/videos with correct headers and body", async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      json: async () => ({ video_id: "vid-1", upload_url: "https://signed.url" }),
    });

    await repo.initiateUpload(
      {
        title: "My Video",
        description: "A test video",
        categoryId: 3,
        tags: ["go", "tutorial"],
        file: mockFile,
      },
      "test-token"
    );

    expect(mockFetch).toHaveBeenCalledTimes(1);
    const [url, options] = mockFetch.mock.calls[0];
    expect(url).toBe("https://api.example.com/api/videos");
    expect(options.method).toBe("POST");
    expect(options.headers["Authorization"]).toBe("Bearer test-token");
    expect(options.headers["Content-Type"]).toBe("application/json");

    const body = JSON.parse(options.body);
    expect(body.title).toBe("My Video");
    expect(body.description).toBe("A test video");
    expect(body.category_id).toBe(3);
    expect(body.tags).toEqual(["go", "tutorial"]);
    expect(body.mime_type).toBe("video/mp4");
  });

  it("returns video_id and upload_url on success", async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      json: async () => ({
        video_id: "00000000-0000-0000-0000-000000000001",
        upload_url: "https://storage.googleapis.com/bucket/raw/uid/vid?sig=abc",
      }),
    });

    const result = await repo.initiateUpload(
      {
        title: "My Video",
        description: "",
        categoryId: null,
        tags: [],
        file: mockFile,
      },
      "token"
    );

    expect(result.videoId).toBe("00000000-0000-0000-0000-000000000001");
    expect(result.uploadUrl).toBe(
      "https://storage.googleapis.com/bucket/raw/uid/vid?sig=abc"
    );
  });

  it("throws with error message from API response body on failure", async () => {
    mockFetch.mockResolvedValue({
      ok: false,
      status: 422,
      json: async () => ({ error: "title is required" }),
    });

    await expect(
      repo.initiateUpload(
        {
          title: "",
          description: "",
          categoryId: null,
          tags: [],
          file: mockFile,
        },
        "token"
      )
    ).rejects.toThrow("title is required");
  });

  it("throws fallback message when error response has no error field", async () => {
    mockFetch.mockResolvedValue({
      ok: false,
      status: 500,
      json: async () => ({}),
    });

    await expect(
      repo.initiateUpload(
        {
          title: "Title",
          description: "",
          categoryId: null,
          tags: [],
          file: mockFile,
        },
        "token"
      )
    ).rejects.toThrow("Failed to initiate upload: 500");
  });

  it("sends null category_id when categoryId param is null", async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      json: async () => ({ video_id: "v1", upload_url: "https://url" }),
    });

    await repo.initiateUpload(
      {
        title: "Title",
        description: "",
        categoryId: null,
        tags: [],
        file: mockFile,
      },
      "token"
    );

    const body = JSON.parse(mockFetch.mock.calls[0][1].body);
    expect(body.category_id).toBeNull();
  });

  it("uses the default API_URL when no base URL is passed to constructor", async () => {
    const defaultRepo = new ApiVideoUploadRepository();
    mockFetch.mockResolvedValue({
      ok: true,
      json: async () => ({ video_id: "v1", upload_url: "https://url" }),
    });

    await defaultRepo.initiateUpload(
      {
        title: "Title",
        description: "",
        categoryId: null,
        tags: [],
        file: mockFile,
      },
      "token"
    );

    const [url] = mockFetch.mock.calls[0];
    expect(url).toBe("/api/videos");
  });
});
