-- 0008_playlists_is_private.up.sql
-- Add is_private flag to playlists to support playlist privacy settings.

ALTER TABLE playlists ADD COLUMN is_private BOOLEAN NOT NULL DEFAULT FALSE;
