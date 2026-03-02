"use client";

import { use, useState, useEffect } from "react";
import Image from "next/image";
import type { UserProfile, UserProfileRepository } from "@/domain/userProfile";
import { ApiUserProfileRepository } from "@/data/userProfileRepository";

// Default singleton repository used in production.
const defaultRepository: UserProfileRepository = new ApiUserProfileRepository();

interface UserProfilePageProps {
  // Next.js 15+ passes params as a Promise; unwrap with React.use().
  params: Promise<{ username: string }>;
  // Optional repository for dependency injection (e.g. in tests).
  repository?: UserProfileRepository;
}

export default function UserProfilePage({
  params,
  repository = defaultRepository,
}: UserProfilePageProps) {
  const { username } = use(params);

  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [notFound, setNotFound] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

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
