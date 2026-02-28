-- 0001_initial_schema.down.sql
-- Drop all core tables in reverse dependency order

DROP INDEX IF EXISTS idx_ratings_user_id;
DROP TABLE IF EXISTS ratings;

DROP INDEX IF EXISTS idx_comments_author_id;
DROP INDEX IF EXISTS idx_comments_video_id;
DROP TABLE IF EXISTS comments;

DROP TABLE IF EXISTS playlist_videos;

DROP INDEX IF EXISTS idx_playlists_owner_id;
DROP TABLE IF EXISTS playlists;

DROP TABLE IF EXISTS video_tags;
DROP TABLE IF EXISTS categories;

DROP TRIGGER IF EXISTS trg_videos_updated_at ON videos;
DROP INDEX IF EXISTS idx_videos_uploader_id;
DROP TABLE IF EXISTS videos;

DROP FUNCTION IF EXISTS set_updated_at();
DROP TABLE IF EXISTS users;
