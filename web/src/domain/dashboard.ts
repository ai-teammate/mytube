// Domain layer: entities, use-case interfaces, and repository interfaces for
// the video management dashboard. No framework dependencies.

/** A single video as returned by the dashboard list endpoint. */
export interface DashboardVideo {
  id: string;
  title: string;
  status: "pending" | "processing" | "ready" | "failed";
  thumbnailUrl: string | null;
  viewCount: number;
  createdAt: string; // ISO-8601
  description: string | null;
  categoryId: number | null;
  tags: string[];
}

/** Repository interface for listing the authenticated user's videos. */
export interface DashboardVideoRepository {
  listMyVideos(token: string): Promise<DashboardVideo[]>;
}

/** Params accepted by the video update use case. */
export interface UpdateVideoParams {
  title: string;
  description: string;
  categoryId: number | null;
  tags: string[];
}

/** The updated video returned after a successful PUT. */
export interface UpdatedVideo {
  id: string;
  title: string;
  description: string | null;
  status: string;
  thumbnailUrl: string | null;
  viewCount: number;
  tags: string[];
  uploader: { username: string; avatarUrl: string | null };
}

/** Repository interface for mutating a video. */
export interface VideoManagementRepository {
  updateVideo(
    videoId: string,
    params: UpdateVideoParams,
    token: string
  ): Promise<UpdatedVideo>;
  deleteVideo(videoId: string, token: string): Promise<void>;
}
