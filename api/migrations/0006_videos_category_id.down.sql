-- 0006_videos_category_id.down.sql

DROP INDEX IF EXISTS idx_videos_category_id;

ALTER TABLE videos DROP COLUMN IF EXISTS category_id;
