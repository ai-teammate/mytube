// Data layer: HTTP repository implementation for PlaylistRepository.
// Depends only on domain types — no React or Next.js imports.

import type {
  PlaylistDetail,
  PlaylistRepository,
  PlaylistSummary,
} from "@/domain/playlist";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "";

interface RawPlaylistSummary {
  id: string;
  title: string;
  owner_username: string;
  video_count: number;
  created_at: string;
}

interface RawPlaylistVideo {
  id: string;
  title: string;
  thumbnail_url: string | null;
  position: number;
}

interface RawPlaylistDetail {
  id: string;
  title: string;
  owner_username: string;
  videos: RawPlaylistVideo[];
}

function mapSummary(raw: RawPlaylistSummary): PlaylistSummary {
  return {
    id: raw.id,
    title: raw.title,
    ownerUsername: raw.owner_username,
    videoCount: raw.video_count,
    createdAt: raw.created_at,
  };
}

function mapDetail(raw: RawPlaylistDetail): PlaylistDetail {
  return {
    id: raw.id,
    title: raw.title,
    ownerUsername: raw.owner_username,
    videos: (raw.videos ?? []).map((v) => ({
      id: v.id,
      title: v.title,
      thumbnailUrl: v.thumbnail_url ?? null,
      position: v.position,
    })),
  };
}

/**
 * ApiPlaylistRepository manages playlists via the backend API.
 */
export class ApiPlaylistRepository implements PlaylistRepository {
  private readonly baseUrl: string;

  constructor(baseUrl: string = API_URL) {
    this.baseUrl = baseUrl;
  }

  async getByID(playlistID: string): Promise<PlaylistDetail | null> {
    const res = await fetch(
      `${this.baseUrl}/api/playlists/${encodeURIComponent(playlistID)}`
    );
    if (res.status === 404 || res.status === 400) return null;
    if (!res.ok) {
      throw new Error(`Failed to fetch playlist ${playlistID}: ${res.status}`);
    }
    const data: RawPlaylistDetail = await res.json();
    return mapDetail(data);
  }

  async create(title: string, token: string): Promise<PlaylistSummary> {
    const res = await fetch(`${this.baseUrl}/api/playlists`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify({ title }),
    });
    if (!res.ok) {
      throw new Error(`Failed to create playlist: ${res.status}`);
    }
    const data: RawPlaylistSummary = await res.json();
    return mapSummary(data);
  }

  async listMine(token: string): Promise<PlaylistSummary[]> {
    const res = await fetch(`${this.baseUrl}/api/me/playlists`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    if (!res.ok) {
      throw new Error(`Failed to list playlists: ${res.status}`);
    }
    const data: RawPlaylistSummary[] = await res.json();
    return data.map(mapSummary);
  }

  async listByUsername(username: string): Promise<PlaylistSummary[]> {
    const res = await fetch(
      `${this.baseUrl}/api/users/${encodeURIComponent(username)}/playlists`
    );
    if (!res.ok) {
      throw new Error(
        `Failed to list playlists for ${username}: ${res.status}`
      );
    }
    const data: RawPlaylistSummary[] = await res.json();
    return data.map(mapSummary);
  }

  async updateTitle(
    playlistID: string,
    title: string,
    token: string
  ): Promise<PlaylistSummary> {
    const res = await fetch(
      `${this.baseUrl}/api/playlists/${encodeURIComponent(playlistID)}`,
      {
        method: "PUT",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ title }),
      }
    );
    if (!res.ok) {
      throw new Error(`Failed to update playlist ${playlistID}: ${res.status}`);
    }
    const data: RawPlaylistSummary = await res.json();
    return mapSummary(data);
  }

  async deletePlaylist(playlistID: string, token: string): Promise<void> {
    const res = await fetch(
      `${this.baseUrl}/api/playlists/${encodeURIComponent(playlistID)}`,
      {
        method: "DELETE",
        headers: { Authorization: `Bearer ${token}` },
      }
    );
    if (!res.ok) {
      throw new Error(`Failed to delete playlist ${playlistID}: ${res.status}`);
    }
  }

  async addVideo(
    playlistID: string,
    videoID: string,
    token: string
  ): Promise<void> {
    const res = await fetch(
      `${this.baseUrl}/api/playlists/${encodeURIComponent(playlistID)}/videos`,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ video_id: videoID }),
      }
    );
    if (!res.ok) {
      throw new Error(
        `Failed to add video to playlist ${playlistID}: ${res.status}`
      );
    }
  }

  async removeVideo(
    playlistID: string,
    videoID: string,
    token: string
  ): Promise<void> {
    const res = await fetch(
      `${this.baseUrl}/api/playlists/${encodeURIComponent(playlistID)}/videos/${encodeURIComponent(videoID)}`,
      {
        method: "DELETE",
        headers: { Authorization: `Bearer ${token}` },
      }
    );
    if (!res.ok) {
      throw new Error(
        `Failed to remove video from playlist ${playlistID}: ${res.status}`
      );
    }
  }
}
