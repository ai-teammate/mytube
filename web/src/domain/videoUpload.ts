// Domain layer: entities, use-case interface, and repository interface for
// video upload. No framework dependencies.

/** Accepted MIME types for video upload. */
export const ACCEPTED_VIDEO_MIME_TYPES = [
  "video/mp4",
  "video/quicktime",
  "video/x-msvideo",
  "video/webm",
] as const;

/** Client-side file size warning threshold (4 GB). */
export const UPLOAD_SIZE_WARNING_BYTES = 4 * 1024 * 1024 * 1024;

/** Parameters required to initiate a video upload. */
export interface InitiateUploadParams {
  title: string;
  description: string;
  categoryId: number | null;
  tags: string[];
  file: File;
}

/** Result returned after the backend creates the video record. */
export interface InitiateUploadResult {
  videoId: string;
  uploadUrl: string;
}

/** Repository interface for creating a video record and obtaining a signed URL. */
export interface VideoUploadRepository {
  initiateUpload(
    params: InitiateUploadParams,
    token: string
  ): Promise<InitiateUploadResult>;
}

/** Category as used in the upload form. */
export interface Category {
  id: number;
  name: string;
}

/** Repository interface for fetching category list. */
export interface CategoryRepository {
  listCategories(token: string): Promise<Category[]>;
}
