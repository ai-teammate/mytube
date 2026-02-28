// Command transcoder is the Cloud Run Job that transcodes a raw video into
// multi-bitrate HLS, extracts a thumbnail, and updates the database record.
//
// Required environment variables:
//
//	VIDEO_ID        — UUID of the video row in the database
//	RAW_BUCKET      — GCS bucket containing the raw upload (e.g. mytube-raw-uploads)
//	RAW_OBJECT_PATH — object path within RAW_BUCKET (e.g. raw/<uuid>.mp4)
//	HLS_BUCKET      — destination GCS bucket for HLS output (e.g. mytube-hls-output)
//	CDN_BASE_URL    — base URL for constructing the thumbnail_url written to the DB
//	                  (e.g. https://cdn.example.com)
//
// Database connection (same as api service, using Cloud SQL Unix socket):
//
//	INSTANCE_UNIX_SOCKET — Cloud SQL Unix socket path (when running on Cloud Run)
//	DB_USER, DB_PASSWORD, DB_NAME — credentials (same as API)
package main

import (
	"context"
	"fmt"
	"log"
	"os"
	"path/filepath"

	"cloud.google.com/go/storage"
	"github.com/ai-teammate/mytube/api/cmd/transcoder/internal/ffmpeg"
	gcsStorage "github.com/ai-teammate/mytube/api/cmd/transcoder/internal/storage"
	"github.com/ai-teammate/mytube/api/cmd/transcoder/internal/video"
	"github.com/ai-teammate/mytube/api/internal/database"
)

func main() {
	if err := run(); err != nil {
		log.Printf("transcoder error: %v", err)
		os.Exit(1)
	}
}

func run() error {
	cfg, err := configFromEnv()
	if err != nil {
		return fmt.Errorf("config: %w", err)
	}

	ctx := context.Background()

	// Initialise GCS client.
	gcsClient, err := storage.NewClient(ctx)
	if err != nil {
		return fmt.Errorf("create GCS client: %w", err)
	}
	defer gcsClient.Close()

	// Initialise database.
	db, err := database.Open()
	if err != nil {
		return fmt.Errorf("open db: %w", err)
	}
	defer db.Close()

	repo := video.NewRepository(db)

	downloader := gcsStorage.NewDownloader(gcsStorage.NewGCSObjectReader(gcsClient))
	uploader := gcsStorage.NewUploader(gcsStorage.NewGCSObjectWriter(gcsClient))
	ffmpegRunner := ffmpeg.NewRunner()

	return transcode(ctx, cfg, downloader, uploader, ffmpegRunner, repo)
}

// config holds the job configuration derived from environment variables.
type config struct {
	VideoID       string
	RawBucket     string
	RawObjectPath string
	HLSBucket     string
	CDNBaseURL    string
}

// configFromEnv reads required environment variables into a config.
func configFromEnv() (config, error) {
	vars := map[string]*string{
		"VIDEO_ID":        new(string),
		"RAW_BUCKET":      new(string),
		"RAW_OBJECT_PATH": new(string),
		"HLS_BUCKET":      new(string),
		"CDN_BASE_URL":    new(string),
	}
	for k, v := range vars {
		*v = os.Getenv(k)
		if *v == "" {
			return config{}, fmt.Errorf("required env var %s is not set", k)
		}
	}
	return config{
		VideoID:       *vars["VIDEO_ID"],
		RawBucket:     *vars["RAW_BUCKET"],
		RawObjectPath: *vars["RAW_OBJECT_PATH"],
		HLSBucket:     *vars["HLS_BUCKET"],
		CDNBaseURL:    *vars["CDN_BASE_URL"],
	}, nil
}

// Transcoder groups the dependencies needed for a single transcoding run.
// It is defined here to support dependency injection in tests.
type Transcoder interface {
	TranscodeHLS(ctx context.Context, inputPath, outputDir string, renditions []ffmpeg.Rendition) error
	ExtractThumbnail(ctx context.Context, inputPath, destPath string, offsetSeconds int) error
}

// FileDownloader downloads a raw GCS object to disk.
type FileDownloader interface {
	Download(ctx context.Context, bucket, objectPath, destPath string) error
}

// DirUploader uploads local files to GCS.
type DirUploader interface {
	UploadFile(ctx context.Context, bucket, objectPath, srcPath string) error
	UploadDir(ctx context.Context, bucket, prefix, srcDir string) error
}

// VideoRepository updates video records in the database.
type VideoRepository interface {
	UpdateVideo(ctx context.Context, videoID string, u video.Update) error
	MarkFailed(ctx context.Context, videoID string) error
}

// transcode executes the full transcoding pipeline for one video.
// The working directory is a temporary directory that is cleaned up on return.
// On any failure, transcode makes a best-effort call to repo.MarkFailed before
// returning the original error.
func transcode(
	ctx context.Context,
	cfg config,
	dl FileDownloader,
	ul DirUploader,
	tr Transcoder,
	repo VideoRepository,
) error {
	err := doTranscode(ctx, cfg, dl, ul, tr, repo)
	if err != nil {
		if markErr := repo.MarkFailed(ctx, cfg.VideoID); markErr != nil {
			log.Printf("warning: could not mark video %s as failed: %v", cfg.VideoID, markErr)
		}
	}
	return err
}

// doTranscode contains the core pipeline steps.
func doTranscode(
	ctx context.Context,
	cfg config,
	dl FileDownloader,
	ul DirUploader,
	tr Transcoder,
	repo VideoRepository,
) error {
	// Create a temporary working directory.
	workDir, err := os.MkdirTemp("", "transcoder-"+cfg.VideoID+"-*")
	if err != nil {
		return fmt.Errorf("create work dir: %w", err)
	}
	defer os.RemoveAll(workDir)

	// ── Step 1: Download raw file ─────────────────────────────────────────────
	rawPath := filepath.Join(workDir, "raw_input"+filepath.Ext(cfg.RawObjectPath))
	log.Printf("downloading gs://%s/%s → %s", cfg.RawBucket, cfg.RawObjectPath, rawPath)
	if err := dl.Download(ctx, cfg.RawBucket, cfg.RawObjectPath, rawPath); err != nil {
		return fmt.Errorf("download raw file: %w", err)
	}

	// ── Step 2: Transcode to HLS ──────────────────────────────────────────────
	hlsDir := filepath.Join(workDir, "hls")
	if err := os.MkdirAll(hlsDir, 0o755); err != nil {
		return fmt.Errorf("create hls dir: %w", err)
	}
	log.Printf("transcoding %s → %s (HLS)", rawPath, hlsDir)
	if err := tr.TranscodeHLS(ctx, rawPath, hlsDir, ffmpeg.DefaultRenditions()); err != nil {
		return fmt.Errorf("transcode HLS: %w", err)
	}

	// ── Step 3: Extract thumbnail ─────────────────────────────────────────────
	thumbPath := filepath.Join(workDir, "thumbnail.jpg")
	log.Printf("extracting thumbnail from %s → %s", rawPath, thumbPath)
	if err := tr.ExtractThumbnail(ctx, rawPath, thumbPath, 5); err != nil {
		return fmt.Errorf("extract thumbnail: %w", err)
	}

	// ── Step 4: Upload HLS output ─────────────────────────────────────────────
	hlsPrefix := fmt.Sprintf("videos/%s", cfg.VideoID)
	log.Printf("uploading HLS to gs://%s/%s/", cfg.HLSBucket, hlsPrefix)
	if err := ul.UploadDir(ctx, cfg.HLSBucket, hlsPrefix, hlsDir); err != nil {
		return fmt.Errorf("upload HLS: %w", err)
	}

	// ── Step 5: Upload thumbnail ──────────────────────────────────────────────
	thumbObjectPath := fmt.Sprintf("videos/%s/thumbnail.jpg", cfg.VideoID)
	log.Printf("uploading thumbnail to gs://%s/%s", cfg.HLSBucket, thumbObjectPath)
	if err := ul.UploadFile(ctx, cfg.HLSBucket, thumbObjectPath, thumbPath); err != nil {
		return fmt.Errorf("upload thumbnail: %w", err)
	}

	// ── Step 6: Update database ───────────────────────────────────────────────
	hlsManifestPath := fmt.Sprintf("gs://%s/videos/%s/index.m3u8", cfg.HLSBucket, cfg.VideoID)
	thumbnailURL := fmt.Sprintf("%s/videos/%s/thumbnail.jpg", cfg.CDNBaseURL, cfg.VideoID)

	log.Printf("updating video %s: hls=%s thumb=%s", cfg.VideoID, hlsManifestPath, thumbnailURL)
	if err := repo.UpdateVideo(ctx, cfg.VideoID, video.Update{
		HLSManifestPath: hlsManifestPath,
		ThumbnailURL:    thumbnailURL,
		Status:          video.StatusReady,
	}); err != nil {
		return fmt.Errorf("update video record: %w", err)
	}

	log.Printf("transcoder completed successfully for video %s", cfg.VideoID)
	return nil
}
