"use client";

import { use, useState, useEffect } from "react";
import Image from "next/image";
import Link from "next/link";
import type { UserProfile, UserProfileRepository } from "@/domain/userProfile";
import type { PlaylistRepository, PlaylistSummary } from "@/domain/playlist";
import { ApiUserProfileRepository } from "@/data/userProfileRepository";
import { ApiPlaylistRepository } from "@/data/playlistRepository";

// Default singleton repositories used in production.
const defaultRepository: UserProfileRepository = new ApiUserProfileRepository();
const defaultPlaylistRepository: PlaylistRepository = new ApiPlaylistRepository();

interface UserProfilePageProps {
  // Next.js 15+ passes params as a Promise; unwrap with React.use().
  params: Promise<{ username: string }>;
  // Optional repositories for dependency injection (e.g. in tests).
  repository?: UserProfileRepository;
  playlistRepository?: PlaylistRepository;
}

export default function UserProfilePage({
  params,
  repository = defaultRepository,
  playlistRepository = defaultPlaylistRepository,
}: UserProfilePageProps) {
  const { username } = use(params);

  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [notFound, setNotFound] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  // Tab state
  const [activeTab, setActiveTab] = useState<"videos" | "playlists">("videos");

  // Playlists state
  const [playlists, setPlaylists] = useState<PlaylistSummary[]>([]);
  const [playlistsLoading, setPlaylistsLoading] = useState(false);
  const [playlistsLoaded, setPlaylistsLoaded] = useState(false);

  useEffect(() => {
    let cancelled = false;

    async function loadProfile() {
      try {
        const data = await repository.getByUsername(username);
        if (cancelled) return;
        if (data === null) {
          setNotFound(true);
        } else {
          setProfile(data);
        }
      } catch {
        if (!cancelled) {
          setError("Could not load profile. Please try again later.");
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    loadProfile();
    return () => {
      cancelled = true;
    };
  }, [username, repository]);

  // Load playlists when the playlists tab is first activated.
  useEffect(() => {
    if (activeTab !== "playlists" || playlistsLoaded) return;
    let cancelled = false;

    async function loadPlaylists() {
      setPlaylistsLoading(true);
      try {
        const data = await playlistRepository.listByUsername(username);
        if (!cancelled) {
          setPlaylists(data);
          setPlaylistsLoaded(true);
        }
      } catch {
        if (!cancelled) setPlaylistsLoaded(true); // still mark as loaded to stop spinner
      } finally {
        if (!cancelled) setPlaylistsLoading(false);
      }
    }

    loadPlaylists();
    return () => {
      cancelled = true;
    };
  }, [activeTab, username, playlistRepository, playlistsLoaded]);

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <p className="text-gray-500">Loading…</p>
      </div>
    );
  }

  if (notFound) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <p className="text-gray-500">User not found.</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <p role="alert" className="text-red-600">
          {error}
        </p>
      </div>
    );
  }

  if (!profile) return null;

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Profile header */}
      <div className="max-w-5xl mx-auto px-4 py-8">
        <div className="flex items-center gap-4 mb-6">
          {profile.avatarUrl ? (
            <Image
              src={profile.avatarUrl}
              alt={`${profile.username}'s avatar`}
              width={80}
              height={80}
              className="rounded-full object-cover"
            />
          ) : (
            <div
              className="w-20 h-20 rounded-full bg-gray-300 flex items-center justify-center text-2xl font-bold text-gray-600"
              aria-label={`${profile.username}'s avatar`}
            >
              {profile.username.charAt(0).toUpperCase()}
            </div>
          )}
          <h1 className="text-2xl font-bold text-gray-900">
            {profile.username}
          </h1>
        </div>

        {/* Tabs */}
        <div className="border-b border-gray-200 mb-6">
          <nav className="-mb-px flex gap-6">
            <button
              onClick={() => setActiveTab("videos")}
              className={`pb-2 text-sm font-medium border-b-2 transition-colors ${
                activeTab === "videos"
                  ? "border-blue-600 text-blue-600"
                  : "border-transparent text-gray-500 hover:text-gray-700"
              }`}
            >
              Videos
            </button>
            <button
              onClick={() => setActiveTab("playlists")}
              className={`pb-2 text-sm font-medium border-b-2 transition-colors ${
                activeTab === "playlists"
                  ? "border-blue-600 text-blue-600"
                  : "border-transparent text-gray-500 hover:text-gray-700"
              }`}
            >
              Playlists
            </button>
          </nav>
        </div>

        {/* Videos tab */}
        {activeTab === "videos" && (
          <>
            {/* Cap notice: shown only when exactly 50 videos are returned.
                NOTE: This heuristic will also trigger for users who genuinely have
                exactly 50 videos.  This is the accepted MVP behaviour per MYTUBE-91
                Option B.  A follow-up ticket should add a `has_more` field to the
                API response to eliminate the ambiguity. */}
            {profile.videos.length === 50 && (
              <p className="text-sm text-gray-500 mb-4">
                Showing the 50 most recent videos
              </p>
            )}

            {/* Video grid */}
            {profile.videos.length === 0 ? (
              <p className="text-gray-500">No videos yet.</p>
            ) : (
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
                {profile.videos.map((video) => (
                  <Link
                    key={video.id}
                    href={`/v/${video.id}`}
                    className="block rounded-lg overflow-hidden bg-white shadow hover:shadow-md transition-shadow"
                  >
                    <div className="relative w-full aspect-video bg-gray-200">
                      {video.thumbnailUrl ? (
                        <Image
                          src={video.thumbnailUrl}
                          alt={video.title}
                          fill
                          className="object-cover"
                        />
                      ) : (
                        <div className="w-full h-full flex items-center justify-center text-gray-400 text-sm">
                          No thumbnail
                        </div>
                      )}
                    </div>
                    <div className="p-3">
                      <p className="text-sm font-medium text-gray-900 line-clamp-2">
                        {video.title}
                      </p>
                      <p className="text-xs text-gray-500 mt-1">
                        {video.viewCount.toLocaleString()} views ·{" "}
                        {new Date(video.createdAt).toLocaleDateString()}
                      </p>
                    </div>
                  </Link>
                ))}
              </div>
            )}
          </>
        )}

        {/* Playlists tab */}
        {activeTab === "playlists" && (
          <>
            {playlistsLoading ? (
              <p className="text-gray-500">Loading playlists…</p>
            ) : playlists.length === 0 ? (
              <p className="text-gray-500">No playlists yet.</p>
            ) : (
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
                {playlists.map((pl) => (
                  <Link
                    key={pl.id}
                    href={`/pl/${pl.id}`}
                    className="block rounded-lg overflow-hidden bg-white shadow hover:shadow-md transition-shadow"
                  >
                    <div className="p-4">
                      {/* Playlist icon / placeholder */}
                      <div className="w-full aspect-video bg-gray-100 rounded mb-3 flex items-center justify-center text-gray-400">
                        <svg
                          xmlns="http://www.w3.org/2000/svg"
                          fill="none"
                          viewBox="0 0 24 24"
                          strokeWidth={1.5}
                          stroke="currentColor"
                          className="w-10 h-10"
                          aria-hidden="true"
                        >
                          <path
                            strokeLinecap="round"
                            strokeLinejoin="round"
                            d="M3.75 12h16.5m-16.5 3.75h16.5M3.75 19.5h16.5M5.625 4.5h12.75a1.875 1.875 0 010 3.75H5.625a1.875 1.875 0 010-3.75z"
                          />
                        </svg>
                      </div>
                      <p className="text-sm font-medium text-gray-900 line-clamp-2">
                        {pl.title}
                      </p>
                      <p className="text-xs text-gray-500 mt-1">
                        {pl.videoCount} videos
                      </p>
                    </div>
                  </Link>
                ))}
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
