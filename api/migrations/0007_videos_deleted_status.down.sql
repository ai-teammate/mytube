-- 0007_videos_deleted_status.down.sql
-- Remove 'deleted' from the videos status check constraint.

-- Fail fast if any rows still have status = 'deleted' — cannot re-add stricter constraint.
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM videos WHERE status = 'deleted') THEN
        RAISE EXCEPTION 'Cannot rollback migration: % row(s) with status=''deleted'' exist. Update or remove them first.',
            (SELECT COUNT(*) FROM videos WHERE status = 'deleted');
    END IF;
END $$;

ALTER TABLE videos DROP CONSTRAINT IF EXISTS videos_status_check;

ALTER TABLE videos ADD CONSTRAINT videos_status_check
    CHECK (status IN ('pending', 'processing', 'ready', 'failed'));

