-- 0006_videos_category_id.up.sql
-- Add category_id foreign key to videos table as decided in MYTUBE-93 Option A.
-- The column is nullable so existing video rows are unaffected.

ALTER TABLE videos
    ADD COLUMN IF NOT EXISTS category_id INT REFERENCES categories(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_videos_category_id ON videos(category_id);
