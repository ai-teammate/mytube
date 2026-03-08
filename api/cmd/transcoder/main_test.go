package main

import (
	"context"
	"errors"
	"fmt"
	"io"
	"os"
	"path/filepath"
	"strings"
	"testing"

	"github.com/ai-teammate/mytube/api/cmd/transcoder/internal/ffmpeg"
	"github.com/ai-teammate/mytube/api/cmd/transcoder/internal/video"
)

// ── stub implementations ──────────────────────────────────────────────────────

// stubDownloader implements FileDownloader.
type stubDownloader struct {
	err          error
	downloadedTo string // records the destPath
	content      string // written to destPath on success
}

func (s *stubDownloader) Download(_ context.Context, _, _, destPath string) error {
	s.downloadedTo = destPath
	if s.err != nil {
		return s.err
	}
	// Write dummy content so ffmpeg can find the file.
	return os.WriteFile(destPath, []byte(s.content), 0o644)
}

// stubUploader implements DirUploader.
type stubUploader struct {
	fileErr      error
	dirErr       error
	uploadedFiles []string
	uploadedDirs  []string
}

func (s *stubUploader) UploadFile(_ context.Context, _, objectPath, _ string) error {
	s.uploadedFiles = append(s.uploadedFiles, objectPath)
	return s.fileErr
}

func (s *stubUploader) UploadDir(_ context.Context, _, prefix, _ string) error {
	s.uploadedDirs = append(s.uploadedDirs, prefix)
	return s.dirErr
}

// stubTranscoder implements Transcoder.
type stubTranscoder struct {
	hlsErr          error
	thumbErr        error
	// silentThumbFail simulates FFmpeg exiting 0 but producing no thumbnail file.
	silentThumbFail bool
	calls           []string
}

func (s *stubTranscoder) TranscodeHLS(_ context.Context, _, outputDir string, _ []ffmpeg.Rendition) error {
	s.calls = append(s.calls, "TranscodeHLS")
	if s.hlsErr != nil {
		return s.hlsErr
	}
	// Create index.m3u8 so upload can proceed.
	return os.WriteFile(filepath.Join(outputDir, "index.m3u8"), []byte("#EXTM3U"), 0o644)
}

func (s *stubTranscoder) ExtractThumbnail(_ context.Context, _, destPath string, _ int) error {
	s.calls = append(s.calls, "ExtractThumbnail")
	if s.thumbErr != nil {
		return s.thumbErr
	}
	if s.silentThumbFail {
		// Simulate FFmpeg exiting 0 but not writing the thumbnail file.
		return nil
	}
	return os.WriteFile(destPath, []byte("jpeg"), 0o644)
}

// stubVideoRepo implements VideoRepository.
type stubVideoRepo struct {
	updateErr    error
	markFailErr  error
	updateCalled bool
	markFailed   bool
	lastUpdate   video.Update
	lastVideoID  string
}

func (s *stubVideoRepo) UpdateVideo(_ context.Context, videoID string, u video.Update) error {
	s.updateCalled = true
	s.lastVideoID = videoID
	s.lastUpdate = u
	return s.updateErr
}

func (s *stubVideoRepo) MarkFailed(_ context.Context, _ string) error {
	s.markFailed = true
	return s.markFailErr
}

// stubCleaner implements HLSCleaner.
type stubCleaner struct {
	deletedPrefixes []string
	err             error
}

func (s *stubCleaner) DeletePrefix(_ context.Context, bucket, prefix string) error {
	s.deletedPrefixes = append(s.deletedPrefixes, bucket+"/"+prefix)
	return s.err
}

// ── helpers ───────────────────────────────────────────────────────────────────

func newTestConfig() config {
	return config{
		VideoID:                   "test-video-id",
		RawBucket:                 "raw-bucket",
		RawObjectPath:             "raw/test-video-id.mp4",
		HLSBucket:                 "hls-bucket",
		CDNBaseURL:                "https://cdn.example.com",
		CleanupOnTranscodeFailure: true,
	}
}

// ── transcode happy path ──────────────────────────────────────────────────────

func TestTranscode_HappyPath_NoError(t *testing.T) {
	dl := &stubDownloader{content: "video"}
	ul := &stubUploader{}
	tr := &stubTranscoder{}
	repo := &stubVideoRepo{}

	if err := transcode(context.Background(), newTestConfig(), dl, ul, &stubCleaner{}, tr, repo); err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
}

func TestTranscode_HappyPath_CallsAllSteps(t *testing.T) {
	dl := &stubDownloader{content: "video"}
	ul := &stubUploader{}
	tr := &stubTranscoder{}
	repo := &stubVideoRepo{}

	_ = transcode(context.Background(), newTestConfig(), dl, ul, &stubCleaner{}, tr, repo)

	if dl.downloadedTo == "" {
		t.Error("Download was not called")
	}
	if !contains(tr.calls, "TranscodeHLS") {
		t.Error("TranscodeHLS was not called")
	}
	if !contains(tr.calls, "ExtractThumbnail") {
		t.Error("ExtractThumbnail was not called")
	}
	if !repo.updateCalled {
		t.Error("UpdateVideo was not called")
	}
}

func TestTranscode_HappyPath_UpdatesDBWithCorrectPaths(t *testing.T) {
	cfg := newTestConfig()
	dl := &stubDownloader{content: "video"}
	ul := &stubUploader{}
	tr := &stubTranscoder{}
	repo := &stubVideoRepo{}

	_ = transcode(context.Background(), cfg, dl, ul, &stubCleaner{}, tr, repo)

	wantHLS := fmt.Sprintf("gs://%s/videos/%s/index.m3u8", cfg.HLSBucket, cfg.VideoID)
	if repo.lastUpdate.HLSManifestPath != wantHLS {
		t.Errorf("HLSManifestPath = %q, want %q", repo.lastUpdate.HLSManifestPath, wantHLS)
	}
	wantThumb := fmt.Sprintf("%s/videos/%s/thumbnail.jpg", cfg.CDNBaseURL, cfg.VideoID)
	if repo.lastUpdate.ThumbnailURL != wantThumb {
		t.Errorf("ThumbnailURL = %q, want %q", repo.lastUpdate.ThumbnailURL, wantThumb)
	}
}

func TestTranscode_HappyPath_UpdatesDBWithStatusReady(t *testing.T) {
	dl := &stubDownloader{content: "video"}
	ul := &stubUploader{}
	tr := &stubTranscoder{}
	repo := &stubVideoRepo{}

	_ = transcode(context.Background(), newTestConfig(), dl, ul, &stubCleaner{}, tr, repo)

	if repo.lastUpdate.Status != video.StatusReady {
		t.Errorf("status = %q, want %q", repo.lastUpdate.Status, video.StatusReady)
	}
}

func TestTranscode_HappyPath_UploadsHLSAndThumbnail(t *testing.T) {
	cfg := newTestConfig()
	dl := &stubDownloader{content: "video"}
	ul := &stubUploader{}
	tr := &stubTranscoder{}
	repo := &stubVideoRepo{}

	_ = transcode(context.Background(), cfg, dl, ul, &stubCleaner{}, tr, repo)

	wantDir := fmt.Sprintf("videos/%s", cfg.VideoID)
	if len(ul.uploadedDirs) == 0 || ul.uploadedDirs[0] != wantDir {
		t.Errorf("uploaded HLS dir = %v, want [%s]", ul.uploadedDirs, wantDir)
	}
	wantThumbObj := fmt.Sprintf("videos/%s/thumbnail.jpg", cfg.VideoID)
	found := false
	for _, f := range ul.uploadedFiles {
		if f == wantThumbObj {
			found = true
			break
		}
	}
	if !found {
		t.Errorf("thumbnail not uploaded; uploadedFiles = %v", ul.uploadedFiles)
	}
}

// ── transcode error cases ─────────────────────────────────────────────────────

func TestTranscode_DownloadError_ReturnsError(t *testing.T) {
	dl := &stubDownloader{err: errors.New("download failed")}
	ul := &stubUploader{}
	tr := &stubTranscoder{}
	repo := &stubVideoRepo{}

	err := transcode(context.Background(), newTestConfig(), dl, ul, &stubCleaner{}, tr, repo)
	if err == nil {
		t.Fatal("expected error, got nil")
	}
}

func TestTranscode_DownloadError_MarksVideoFailed(t *testing.T) {
	dl := &stubDownloader{err: errors.New("network timeout")}
	ul := &stubUploader{}
	tr := &stubTranscoder{}
	repo := &stubVideoRepo{}

	_ = transcode(context.Background(), newTestConfig(), dl, ul, &stubCleaner{}, tr, repo)

	if !repo.markFailed {
		t.Error("expected MarkFailed to be called after download error")
	}
}

func TestTranscode_TranscodeHLSError_ReturnsError(t *testing.T) {
	dl := &stubDownloader{content: "video"}
	ul := &stubUploader{}
	tr := &stubTranscoder{hlsErr: errors.New("ffmpeg error")}
	repo := &stubVideoRepo{}

	err := transcode(context.Background(), newTestConfig(), dl, ul, &stubCleaner{}, tr, repo)
	if err == nil {
		t.Fatal("expected error, got nil")
	}
}

func TestTranscode_TranscodeHLSError_MarksVideoFailed(t *testing.T) {
	dl := &stubDownloader{content: "video"}
	ul := &stubUploader{}
	tr := &stubTranscoder{hlsErr: errors.New("codec error")}
	repo := &stubVideoRepo{}

	_ = transcode(context.Background(), newTestConfig(), dl, ul, &stubCleaner{}, tr, repo)

	if !repo.markFailed {
		t.Error("expected MarkFailed to be called after transcode error")
	}
}

// TestTranscode_ThumbnailError_DoesNotAbortJob verifies that a thumbnail extraction
// failure is non-fatal: the job must succeed and HLS output must be preserved.
// Regression test for MYTUBE-384.
func TestTranscode_ThumbnailError_DoesNotAbortJob(t *testing.T) {
	dl := &stubDownloader{content: "video"}
	ul := &stubUploader{}
	tr := &stubTranscoder{thumbErr: errors.New("thumbnail error")}
	repo := &stubVideoRepo{}

	err := transcode(context.Background(), newTestConfig(), dl, ul, &stubCleaner{}, tr, repo)
	if err != nil {
		t.Fatalf("expected no error when thumbnail extraction fails, got: %v", err)
	}
}

// TestTranscode_ThumbnailError_DoesNotMarkFailed verifies that a thumbnail error
// does not mark the video as failed (thumbnail is non-fatal).
// Regression test for MYTUBE-384.
func TestTranscode_ThumbnailError_DoesNotMarkFailed(t *testing.T) {
	dl := &stubDownloader{content: "video"}
	ul := &stubUploader{}
	tr := &stubTranscoder{thumbErr: errors.New("thumbnail error")}
	repo := &stubVideoRepo{}

	_ = transcode(context.Background(), newTestConfig(), dl, ul, &stubCleaner{}, tr, repo)

	if repo.markFailed {
		t.Error("MarkFailed must not be called when only the thumbnail fails")
	}
}

// TestTranscode_ThumbnailError_DoesNotCleanUpHLS verifies that a thumbnail error
// does not trigger HLS cleanup (thumbnail is non-fatal, HLS output must be preserved).
// Regression test for MYTUBE-384.
func TestTranscode_ThumbnailError_DoesNotCleanUpHLS(t *testing.T) {
	dl := &stubDownloader{content: "video"}
	ul := &stubUploader{}
	tr := &stubTranscoder{thumbErr: errors.New("thumbnail error")}
	repo := &stubVideoRepo{}
	cleaner := &stubCleaner{}

	_ = transcode(context.Background(), newTestConfig(), dl, ul, cleaner, tr, repo)

	if len(cleaner.deletedPrefixes) != 0 {
		t.Errorf("HLS must not be cleaned up when only the thumbnail fails, got deletedPrefixes=%v", cleaner.deletedPrefixes)
	}
}

// TestTranscode_SilentThumbnailFailure_SucceedsWithoutThumbnail verifies the
// exact bug from MYTUBE-384: when FFmpeg exits 0 but produces no thumbnail file,
// the job must still succeed (HLS upload and DB update must complete).
func TestTranscode_SilentThumbnailFailure_SucceedsWithoutThumbnail(t *testing.T) {
	dl := &stubDownloader{content: "video"}
	ul := &stubUploader{}
	tr := &stubTranscoder{silentThumbFail: true}
	repo := &stubVideoRepo{}

	err := transcode(context.Background(), newTestConfig(), dl, ul, &stubCleaner{}, tr, repo)
	if err != nil {
		t.Fatalf("expected no error for silent thumbnail failure, got: %v", err)
	}
	if !repo.updateCalled {
		t.Error("UpdateVideo must be called even when thumbnail is missing")
	}
}

// TestTranscode_SilentThumbnailFailure_NoThumbnailUpload verifies that when FFmpeg
// exits 0 but writes no thumbnail file, no thumbnail upload is attempted.
// Regression test for MYTUBE-384.
func TestTranscode_SilentThumbnailFailure_NoThumbnailUpload(t *testing.T) {
	cfg := newTestConfig()
	dl := &stubDownloader{content: "video"}
	ul := &stubUploader{}
	tr := &stubTranscoder{silentThumbFail: true}
	repo := &stubVideoRepo{}

	_ = transcode(context.Background(), cfg, dl, ul, &stubCleaner{}, tr, repo)

	wantThumbObj := fmt.Sprintf("videos/%s/thumbnail.jpg", cfg.VideoID)
	for _, f := range ul.uploadedFiles {
		if f == wantThumbObj {
			t.Errorf("thumbnail must not be uploaded when thumbnail file was not written, but found %q in uploadedFiles", f)
		}
	}
}

// TestTranscode_SilentThumbnailFailure_EmptyThumbnailURLInDB verifies that when
// no thumbnail is produced, the DB record is updated with an empty thumbnail URL.
// Regression test for MYTUBE-384.
func TestTranscode_SilentThumbnailFailure_EmptyThumbnailURLInDB(t *testing.T) {
	dl := &stubDownloader{content: "video"}
	ul := &stubUploader{}
	tr := &stubTranscoder{silentThumbFail: true}
	repo := &stubVideoRepo{}

	_ = transcode(context.Background(), newTestConfig(), dl, ul, &stubCleaner{}, tr, repo)

	if repo.lastUpdate.ThumbnailURL != "" {
		t.Errorf("ThumbnailURL must be empty when thumbnail was not produced, got %q", repo.lastUpdate.ThumbnailURL)
	}
}

// TestTranscode_SilentThumbnailFailure_HLSUploaded verifies that HLS output is
// uploaded successfully even when thumbnail extraction silently fails.
// Regression test for MYTUBE-384.
func TestTranscode_SilentThumbnailFailure_HLSUploaded(t *testing.T) {
	cfg := newTestConfig()
	dl := &stubDownloader{content: "video"}
	ul := &stubUploader{}
	tr := &stubTranscoder{silentThumbFail: true}
	repo := &stubVideoRepo{}

	_ = transcode(context.Background(), cfg, dl, ul, &stubCleaner{}, tr, repo)

	wantDir := fmt.Sprintf("videos/%s", cfg.VideoID)
	if len(ul.uploadedDirs) == 0 || ul.uploadedDirs[0] != wantDir {
		t.Errorf("HLS dir must still be uploaded when thumbnail fails; uploadedDirs=%v", ul.uploadedDirs)
	}
}

func TestTranscode_UploadDirError_ReturnsError(t *testing.T) {
	dl := &stubDownloader{content: "video"}
	ul := &stubUploader{dirErr: errors.New("upload dir failed")}
	tr := &stubTranscoder{}
	repo := &stubVideoRepo{}

	err := transcode(context.Background(), newTestConfig(), dl, ul, &stubCleaner{}, tr, repo)
	if err == nil {
		t.Fatal("expected error, got nil")
	}
}

// TestTranscode_UploadFileError_DoesNotAbortJob verifies that a thumbnail upload
// failure is non-fatal: the job must succeed and HLS output must be preserved.
// Regression test for MYTUBE-384.
func TestTranscode_UploadFileError_DoesNotAbortJob(t *testing.T) {
	dl := &stubDownloader{content: "video"}
	ul := &stubUploader{fileErr: errors.New("upload file failed")}
	tr := &stubTranscoder{}
	repo := &stubVideoRepo{}

	err := transcode(context.Background(), newTestConfig(), dl, ul, &stubCleaner{}, tr, repo)
	if err != nil {
		t.Fatalf("expected no error when thumbnail upload fails, got: %v", err)
	}
}

func TestTranscode_UpdateVideoError_ReturnsError(t *testing.T) {
	dl := &stubDownloader{content: "video"}
	ul := &stubUploader{}
	tr := &stubTranscoder{}
	repo := &stubVideoRepo{updateErr: errors.New("db error")}

	err := transcode(context.Background(), newTestConfig(), dl, ul, &stubCleaner{}, tr, repo)
	if err == nil {
		t.Fatal("expected error, got nil")
	}
}

func TestTranscode_UploadDirError_MarksVideoFailed(t *testing.T) {
	dl := &stubDownloader{content: "video"}
	ul := &stubUploader{dirErr: errors.New("upload dir failed")}
	tr := &stubTranscoder{}
	repo := &stubVideoRepo{}

	_ = transcode(context.Background(), newTestConfig(), dl, ul, &stubCleaner{}, tr, repo)

	if !repo.markFailed {
		t.Error("expected MarkFailed to be called after upload dir error")
	}
}

func TestTranscode_UpdateVideoError_MarksVideoFailed(t *testing.T) {
	dl := &stubDownloader{content: "video"}
	ul := &stubUploader{}
	tr := &stubTranscoder{}
	repo := &stubVideoRepo{updateErr: errors.New("db error")}

	_ = transcode(context.Background(), newTestConfig(), dl, ul, &stubCleaner{}, tr, repo)

	if !repo.markFailed {
		t.Error("expected MarkFailed to be called after UpdateVideo error")
	}
}

// ── configFromEnv ─────────────────────────────────────────────────────────────

func setEnvVars(t *testing.T, pairs map[string]string) {
	t.Helper()
	for k, v := range pairs {
		t.Setenv(k, v)
	}
}

func fullEnv() map[string]string {
	return map[string]string{
		"VIDEO_ID":        "vid-123",
		"RAW_BUCKET":      "raw-bucket",
		"RAW_OBJECT_PATH": "raw/vid-123.mp4",
		"HLS_BUCKET":      "hls-bucket",
		"CDN_BASE_URL":    "https://cdn.example.com",
	}
}

func TestConfigFromEnv_AllVarsSet(t *testing.T) {
	setEnvVars(t, fullEnv())

	cfg, err := configFromEnv()
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if cfg.VideoID != "vid-123" {
		t.Errorf("VideoID = %q, want %q", cfg.VideoID, "vid-123")
	}
	if cfg.RawBucket != "raw-bucket" {
		t.Errorf("RawBucket = %q, want %q", cfg.RawBucket, "raw-bucket")
	}
	if cfg.RawObjectPath != "raw/vid-123.mp4" {
		t.Errorf("RawObjectPath = %q, want %q", cfg.RawObjectPath, "raw/vid-123.mp4")
	}
	if cfg.HLSBucket != "hls-bucket" {
		t.Errorf("HLSBucket = %q, want %q", cfg.HLSBucket, "hls-bucket")
	}
	if cfg.CDNBaseURL != "https://cdn.example.com" {
		t.Errorf("CDNBaseURL = %q, want %q", cfg.CDNBaseURL, "https://cdn.example.com")
	}
	// CleanupOnTranscodeFailure defaults to true when env var is not set.
	if !cfg.CleanupOnTranscodeFailure {
		t.Error("CleanupOnTranscodeFailure should default to true")
	}
}

func TestConfigFromEnv_CleanupDisabled(t *testing.T) {
	setEnvVars(t, fullEnv())
	t.Setenv("CLEANUP_ON_TRANSCODE_FAILURE", "false")

	cfg, err := configFromEnv()
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if cfg.CleanupOnTranscodeFailure {
		t.Error("CleanupOnTranscodeFailure should be false when env var is 'false'")
	}
}

func TestConfigFromEnv_MissingVideoID(t *testing.T) {
	env := fullEnv()
	delete(env, "VIDEO_ID")
	setEnvVars(t, env)
	t.Setenv("VIDEO_ID", "")

	_, err := configFromEnv()
	if err == nil {
		t.Fatal("expected error for missing VIDEO_ID")
	}
}

func TestConfigFromEnv_MissingRawBucket(t *testing.T) {
	env := fullEnv()
	setEnvVars(t, env)
	t.Setenv("RAW_BUCKET", "")

	_, err := configFromEnv()
	if err == nil {
		t.Fatal("expected error for missing RAW_BUCKET")
	}
}

func TestConfigFromEnv_MissingRawObjectPath(t *testing.T) {
	env := fullEnv()
	setEnvVars(t, env)
	t.Setenv("RAW_OBJECT_PATH", "")

	_, err := configFromEnv()
	if err == nil {
		t.Fatal("expected error for missing RAW_OBJECT_PATH")
	}
}

func TestConfigFromEnv_MissingHLSBucket(t *testing.T) {
	env := fullEnv()
	setEnvVars(t, env)
	t.Setenv("HLS_BUCKET", "")

	_, err := configFromEnv()
	if err == nil {
		t.Fatal("expected error for missing HLS_BUCKET")
	}
}

func TestConfigFromEnv_MissingCDNBaseURL(t *testing.T) {
	env := fullEnv()
	setEnvVars(t, env)
	t.Setenv("CDN_BASE_URL", "")

	_, err := configFromEnv()
	if err == nil {
		t.Fatal("expected error for missing CDN_BASE_URL")
	}
}

// ── sanitiseExt ───────────────────────────────────────────────────────────────

func TestSanitiseExt_KnownExtensions(t *testing.T) {
	cases := []struct {
		input string
		want  string
	}{
		{"raw/video.mp4", ".mp4"},
		{"raw/video.MP4", ".mp4"}, // case-insensitive
		{"raw/video.mov", ".mov"},
		{"raw/video.mkv", ".mkv"},
		{"raw/video.webm", ".webm"},
		{"raw/video.avi", ".avi"},
	}
	for _, tc := range cases {
		got := sanitiseExt(tc.input)
		if got != tc.want {
			t.Errorf("sanitiseExt(%q) = %q, want %q", tc.input, got, tc.want)
		}
	}
}

func TestSanitiseExt_UnknownExtension_DefaultsToMp4(t *testing.T) {
	cases := []string{
		"raw/video.flv",
		"raw/video.wmv",
		"raw/video",
		"raw/video.mp4/../../../etc/shadow",
		"",
	}
	for _, input := range cases {
		got := sanitiseExt(input)
		if got != ".mp4" {
			t.Errorf("sanitiseExt(%q) = %q, want .mp4", input, got)
		}
	}
}

// ── HLS cleanup on failure ────────────────────────────────────────────────────

func TestTranscode_Failure_CleansUpHLSPrefix(t *testing.T) {
	cfg := newTestConfig()
	dl := &stubDownloader{err: errors.New("download failed")}
	ul := &stubUploader{}
	cleaner := &stubCleaner{}
	tr := &stubTranscoder{}
	repo := &stubVideoRepo{}

	_ = transcode(context.Background(), cfg, dl, ul, cleaner, tr, repo)

	wantPrefix := "hls-bucket/videos/test-video-id/"
	if len(cleaner.deletedPrefixes) == 0 {
		t.Error("expected HLS prefix to be cleaned up after failure")
	} else if cleaner.deletedPrefixes[0] != wantPrefix {
		t.Errorf("cleaned prefix = %q, want %q", cleaner.deletedPrefixes[0], wantPrefix)
	}
}

func TestTranscode_FailureCleanupDisabled_DoesNotClean(t *testing.T) {
	cfg := newTestConfig()
	cfg.CleanupOnTranscodeFailure = false
	dl := &stubDownloader{err: errors.New("download failed")}
	ul := &stubUploader{}
	cleaner := &stubCleaner{}
	tr := &stubTranscoder{}
	repo := &stubVideoRepo{}

	_ = transcode(context.Background(), cfg, dl, ul, cleaner, tr, repo)

	if len(cleaner.deletedPrefixes) != 0 {
		t.Errorf("expected no cleanup when disabled, got %v", cleaner.deletedPrefixes)
	}
}

func TestTranscode_FailureCleanupError_OriginalErrorReturned(t *testing.T) {
	cfg := newTestConfig()
	originalErr := errors.New("download failed")
	dl := &stubDownloader{err: originalErr}
	ul := &stubUploader{}
	cleaner := &stubCleaner{err: errors.New("GCS cleanup failed")}
	tr := &stubTranscoder{}
	repo := &stubVideoRepo{}

	err := transcode(context.Background(), cfg, dl, ul, cleaner, tr, repo)

	// Cleanup error must not mask the original error.
	if !errors.Is(err, originalErr) {
		t.Errorf("expected original error %v, got %v", originalErr, err)
	}
}

func TestTranscode_HappyPath_DoesNotCleanUp(t *testing.T) {
	cfg := newTestConfig()
	dl := &stubDownloader{content: "video"}
	ul := &stubUploader{}
	cleaner := &stubCleaner{}
	tr := &stubTranscoder{}
	repo := &stubVideoRepo{}

	if err := transcode(context.Background(), cfg, dl, ul, cleaner, tr, repo); err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if len(cleaner.deletedPrefixes) != 0 {
		t.Errorf("expected no cleanup on success, got %v", cleaner.deletedPrefixes)
	}
}

// ── helpers ───────────────────────────────────────────────────────────────────

func contains(slice []string, s string) bool {
	for _, v := range slice {
		if v == s {
			return true
		}
	}
	return false
}

// Ensure unused imports don't break compilation.
var _ = io.NopCloser(strings.NewReader(""))
