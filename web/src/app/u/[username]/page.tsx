"use client";

import { useState, useEffect } from "react";
import Image from "next/image";
import type { UserProfile } from "@/domain/userProfile";
import { ApiUserProfileRepository } from "@/data/userProfileRepository";

// Singleton repository instance — injected via module-level constant so tests
// can mock the data module without touching the component itself.
const profileRepository = new ApiUserProfileRepository();

interface UserProfilePageProps {
  params: { username: string };
}

export default function UserProfilePage({ params }: UserProfilePageProps) {
  const { username } = params;

  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [notFound, setNotFound] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;

    async function loadProfile() {
      try {
        const data = await profileRepository.getByUsername(username);
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
  }, [username]);

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
        <div className="flex items-center gap-4 mb-8">
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

        {/* Cap notice: shown only when 50 videos are returned */}
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
              <a
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
              </a>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
