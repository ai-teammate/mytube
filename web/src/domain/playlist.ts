// Domain layer: entities, use-case interfaces, and repository interfaces for playlists.
// No framework dependencies.

/** A playlist in a list view (summary). */
export interface PlaylistSummary {
  id: string;
  title: string;
  ownerUsername: string;
  videoCount: number;
  createdAt: string; // ISO-8601
}

/** A video item within a playlist. */
export interface PlaylistVideoItem {
  id: string;
  title: string;
  thumbnailUrl: string | null;
  position: number;
}

/** A full playlist with its ordered videos. */
export interface PlaylistDetail {
  id: string;
  title: string;
  ownerUsername: string;
  videos: PlaylistVideoItem[];
}

/** Repository interface for playlist operations. */
export interface PlaylistRepository {
  /** GET /api/playlists/:id — public. */
  getByID(playlistID: string): Promise<PlaylistDetail | null>;

  /** POST /api/playlists — authenticated. */
  create(title: string, token: string): Promise<PlaylistSummary>;

  /** GET /api/me/playlists — authenticated. */
  listMine(token: string): Promise<PlaylistSummary[]>;

  /** GET /api/users/:username/playlists — public. */
  listByUsername(username: string): Promise<PlaylistSummary[]>;

  /** PUT /api/playlists/:id — owner only. */
  updateTitle(playlistID: string, title: string, token: string): Promise<PlaylistSummary>;

  /** DELETE /api/playlists/:id — owner only. */
  deletePlaylist(playlistID: string, token: string): Promise<void>;

  /** POST /api/playlists/:id/videos — owner only. */
  addVideo(playlistID: string, videoID: string, token: string): Promise<void>;

  /** DELETE /api/playlists/:id/videos/:video_id — owner only. */
  removeVideo(playlistID: string, videoID: string, token: string): Promise<void>;
}
