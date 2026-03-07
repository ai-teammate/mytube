-- 0007_videos_deleted_status.up.sql
-- Add 'deleted' to the videos status check constraint to support soft deletes.

ALTER TABLE videos DROP CONSTRAINT IF EXISTS videos_status_check;

ALTER TABLE videos ADD CONSTRAINT videos_status_check
    CHECK (status IN ('pending', 'processing', 'ready', 'failed', 'deleted'));

