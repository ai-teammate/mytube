-- 0001_initial_schema.up.sql
-- Core tables for mytube

CREATE TABLE IF NOT EXISTS users (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    firebase_uid VARCHAR NOT NULL UNIQUE,
    username    VARCHAR(50),
    avatar_url  TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Trigger function: auto-update updated_at on every UPDATE to videos rows.
CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- ON DELETE RESTRICT is used for user-owned content (videos, playlists,
-- comments, ratings) so that deleting a user with existing content raises an
-- explicit FK violation.  Application code must clean up or transfer content
-- before the user row can be removed.
CREATE TABLE IF NOT EXISTS videos (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    uploader_id      UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    title            VARCHAR(255) NOT NULL,
    description      TEXT,
    status           VARCHAR(20) NOT NULL DEFAULT 'pending'
                         CHECK (status IN ('pending','processing','ready','failed')),
    gcs_raw_path     TEXT,
    hls_manifest_path TEXT,
    thumbnail_url    TEXT,
    view_count       BIGINT NOT NULL DEFAULT 0,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TRIGGER trg_videos_updated_at
BEFORE UPDATE ON videos
FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE INDEX idx_videos_uploader_id ON videos(uploader_id);

CREATE TABLE IF NOT EXISTS categories (
    id   SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS video_tags (
    video_id UUID NOT NULL REFERENCES videos(id) ON DELETE CASCADE,
    tag      VARCHAR(100) NOT NULL,
    PRIMARY KEY (video_id, tag)
);

CREATE TABLE IF NOT EXISTS playlists (
    id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    owner_id   UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    title      VARCHAR(255) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_playlists_owner_id ON playlists(owner_id);

CREATE TABLE IF NOT EXISTS playlist_videos (
    playlist_id UUID NOT NULL REFERENCES playlists(id) ON DELETE CASCADE,
    video_id    UUID NOT NULL REFERENCES videos(id) ON DELETE CASCADE,
    position    INT NOT NULL,
    PRIMARY KEY (playlist_id, video_id)
);

CREATE TABLE IF NOT EXISTS comments (
    id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    video_id   UUID NOT NULL REFERENCES videos(id) ON DELETE CASCADE,
    author_id  UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    body       TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_comments_video_id ON comments(video_id);

CREATE TABLE IF NOT EXISTS ratings (
    video_id UUID NOT NULL REFERENCES videos(id) ON DELETE CASCADE,
    user_id  UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    stars    SMALLINT NOT NULL CHECK (stars BETWEEN 1 AND 5),
    PRIMARY KEY (video_id, user_id)
);

CREATE INDEX idx_ratings_user_id ON ratings(user_id);
