// Domain layer: entities and repository interface for the public user profile.
// No framework dependencies.

/** A video as displayed on a public user profile page. */
export interface ProfileVideo {
  id: string;
  title: string;
  thumbnailUrl: string | null;
  viewCount: number;
  createdAt: string; // ISO-8601
}

/** The public profile of a user. */
export interface UserProfile {
  username: string;
  avatarUrl: string | null;
  videos: ProfileVideo[];
}

/** Repository interface for fetching a public user profile. */
export interface UserProfileRepository {
  getByUsername(username: string): Promise<UserProfile | null>;
}
