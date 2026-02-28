-- 0003_search_indexes.down.sql
-- Remove search and discovery indexes

DROP INDEX IF EXISTS videos_status_views;
DROP INDEX IF EXISTS videos_status_created;
DROP INDEX IF EXISTS video_tags_tag_idx;
DROP INDEX IF EXISTS videos_title_fts;
