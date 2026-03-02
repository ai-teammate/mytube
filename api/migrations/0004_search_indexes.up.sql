-- 0003_search_indexes.up.sql
-- Full-text search and performance indexes for search and discovery features

-- GIN index for full-text search on video titles (English language configuration)
CREATE INDEX IF NOT EXISTS videos_title_fts ON videos USING GIN (to_tsvector('english', title));

-- B-tree index on tag column for fast tag-based filtering
CREATE INDEX IF NOT EXISTS video_tags_tag_idx ON video_tags (tag);

-- Composite index for recency queries (e.g. list ready videos ordered by newest first)
CREATE INDEX IF NOT EXISTS videos_status_created ON videos (status, created_at DESC);

-- Composite index for popularity queries (e.g. list ready videos ordered by most viewed)
CREATE INDEX IF NOT EXISTS videos_status_views ON videos (status, view_count DESC);
