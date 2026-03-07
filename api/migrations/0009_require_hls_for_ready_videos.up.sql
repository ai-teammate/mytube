-- 0009_require_hls_for_ready_videos.up.sql
-- Enforce invariant: a video with status='ready' must have a non-null
-- hls_manifest_path. Without this constraint, videos can be marked 'ready'
-- before the transcoder has stored the HLS manifest, causing the watch page
-- to render "Video not available yet." instead of mounting the Video.js player.
--
-- First, reset any existing 'ready' rows that violate the invariant back to
-- 'processing' so the new constraint can be added cleanly. The transcoder will
-- re-process them when triggered.

UPDATE videos
SET    status = 'processing'
WHERE  status = 'ready'
  AND  hls_manifest_path IS NULL;

ALTER TABLE videos
    ADD CONSTRAINT chk_ready_requires_hls
    CHECK (status != 'ready' OR hls_manifest_path IS NOT NULL);
