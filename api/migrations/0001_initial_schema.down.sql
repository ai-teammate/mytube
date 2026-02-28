-- 0001_initial_schema.down.sql
-- Drop all core tables in reverse dependency order

DROP TABLE IF EXISTS ratings;
DROP TABLE IF EXISTS comments;
DROP TABLE IF EXISTS playlist_videos;
DROP TABLE IF EXISTS playlists;
DROP TABLE IF EXISTS video_tags;
DROP TABLE IF EXISTS categories;
DROP TABLE IF EXISTS videos;
DROP TABLE IF EXISTS users;
