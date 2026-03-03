// Data layer: HTTP repository implementation for VideoUploadRepository.
// Depends only on domain types — no React or Next.js imports.

import type {
  InitiateUploadParams,
  InitiateUploadResult,
  VideoUploadRepository,
} from "@/domain/videoUpload";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "";

/**
 * ApiVideoUploadRepository calls POST /api/videos to create a video record
 * and retrieve a GCS signed PUT URL.
 */
export class ApiVideoUploadRepository implements VideoUploadRepository {
  private readonly baseUrl: string;

  constructor(baseUrl: string = API_URL) {
    this.baseUrl = baseUrl;
  }

  async initiateUpload(
    params: InitiateUploadParams,
    token: string
  ): Promise<InitiateUploadResult> {
    const res = await fetch(`${this.baseUrl}/api/videos`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify({
        title: params.title,
        description: params.description,
        category_id: params.categoryId,
        tags: params.tags,
        mime_type: params.file.type,
      }),
    });

    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      throw new Error(body.error ?? `Failed to initiate upload: ${res.status}`);
    }

    const data = await res.json();
    return {
      videoId: data.video_id,
      uploadUrl: data.upload_url,
    };
  }
}
