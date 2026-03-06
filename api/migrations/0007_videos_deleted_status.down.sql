-- 0007_videos_deleted_status.down.sql
-- Remove 'deleted' from the videos status check constraint.
-- NOTE: this will fail if any rows currently have status = 'deleted'.

ALTER TABLE videos DROP CONSTRAINT videos_status_check;

ALTER TABLE videos ADD CONSTRAINT videos_status_check
    CHECK (status IN ('pending', 'processing', 'ready', 'failed'));
