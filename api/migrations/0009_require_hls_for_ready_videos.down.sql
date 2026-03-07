-- 0009_require_hls_for_ready_videos.down.sql
-- Remove the constraint added in the up migration.

ALTER TABLE videos DROP CONSTRAINT IF EXISTS chk_ready_requires_hls;
