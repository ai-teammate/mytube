// Domain layer: entities and repository interface for the video watch page.
// No framework dependencies.

/** Uploader info as returned on the video watch page. */
export interface VideoUploader {
  username: string;
  avatarUrl: string | null;
}

/** Full video details for the watch page. */
export interface VideoDetail {
  id: string;
  title: string;
  description: string | null;
  hlsManifestUrl: string | null;
  thumbnailUrl: string | null;
  viewCount: number;
  createdAt: string; // ISO-8601
  status: string;
  uploader: VideoUploader;
  tags: string[];
}

/** Repository interface for fetching a single video. */
export interface VideoRepository {
  getByID(videoID: string): Promise<VideoDetail | null>;
}
