package storage_test

import (
	"context"
	"errors"
	"io"
	"os"
	"path/filepath"
	"strings"
	"testing"

	"github.com/ai-teammate/mytube/api/cmd/transcoder/internal/storage"
)

// ── stub ObjectReader ──────────────────────────────────────────────────────────

type stubReader struct {
	content string
	err     error
	// recorded calls
	calledBucket string
	calledObject string
}

func (s *stubReader) NewReader(_ context.Context, bucket, object string) (io.ReadCloser, error) {
	s.calledBucket = bucket
	s.calledObject = object
	if s.err != nil {
		return nil, s.err
	}
	return io.NopCloser(strings.NewReader(s.content)), nil
}

// ── stub ObjectWriter ──────────────────────────────────────────────────────────

type stubWriteCloser struct {
	buf          strings.Builder
	closeErr     error
	calledBucket string
	calledObject string
}

func (s *stubWriteCloser) Write(p []byte) (int, error) {
	return s.buf.Write(p)
}

func (s *stubWriteCloser) Close() error {
	return s.closeErr
}

type stubWriter struct {
	wc       *stubWriteCloser
	openErr  error
	calls    []struct{ bucket, object string }
}

func (s *stubWriter) NewWriter(_ context.Context, bucket, object string) io.WriteCloser {
	s.calls = append(s.calls, struct{ bucket, object string }{bucket, object})
	if s.wc != nil {
		s.wc.calledBucket = bucket
		s.wc.calledObject = object
	}
	return s.wc
}

// ── Downloader tests ──────────────────────────────────────────────────────────

func TestDownloader_Download_Success(t *testing.T) {
	dir := t.TempDir()
	destPath := filepath.Join(dir, "output.mp4")

	rdr := &stubReader{content: "video-bytes"}
	dl := storage.NewDownloader(rdr)

	if err := dl.Download(context.Background(), "my-bucket", "raw/video.mp4", destPath); err != nil {
		t.Fatalf("unexpected error: %v", err)
	}

	got, err := os.ReadFile(destPath)
	if err != nil {
		t.Fatalf("read dest file: %v", err)
	}
	if string(got) != "video-bytes" {
		t.Errorf("file content = %q, want %q", string(got), "video-bytes")
	}
}

func TestDownloader_Download_PassesBucketAndObject(t *testing.T) {
	dir := t.TempDir()
	rdr := &stubReader{content: "data"}
	dl := storage.NewDownloader(rdr)

	_ = dl.Download(context.Background(), "bucket-x", "path/to/obj.mp4", filepath.Join(dir, "f"))

	if rdr.calledBucket != "bucket-x" {
		t.Errorf("bucket = %q, want %q", rdr.calledBucket, "bucket-x")
	}
	if rdr.calledObject != "path/to/obj.mp4" {
		t.Errorf("object = %q, want %q", rdr.calledObject, "path/to/obj.mp4")
	}
}

func TestDownloader_Download_ReaderError(t *testing.T) {
	dir := t.TempDir()
	rdr := &stubReader{err: errors.New("GCS error")}
	dl := storage.NewDownloader(rdr)

	err := dl.Download(context.Background(), "b", "o", filepath.Join(dir, "f"))
	if err == nil {
		t.Fatal("expected error, got nil")
	}
}

func TestDownloader_Download_CreatesParentDir(t *testing.T) {
	dir := t.TempDir()
	destPath := filepath.Join(dir, "sub", "dir", "output.mp4")

	rdr := &stubReader{content: "bytes"}
	dl := storage.NewDownloader(rdr)

	if err := dl.Download(context.Background(), "b", "o", destPath); err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if _, err := os.Stat(destPath); err != nil {
		t.Errorf("dest file not created: %v", err)
	}
}

// ── Uploader tests ────────────────────────────────────────────────────────────

func TestUploader_UploadFile_Success(t *testing.T) {
	dir := t.TempDir()
	srcPath := filepath.Join(dir, "src.ts")
	if err := os.WriteFile(srcPath, []byte("segment-data"), 0o644); err != nil {
		t.Fatalf("write src file: %v", err)
	}

	wc := &stubWriteCloser{}
	w := &stubWriter{wc: wc}
	ul := storage.NewUploader(w)

	if err := ul.UploadFile(context.Background(), "my-bucket", "videos/id/0.ts", srcPath); err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if wc.buf.String() != "segment-data" {
		t.Errorf("uploaded content = %q, want %q", wc.buf.String(), "segment-data")
	}
}

func TestUploader_UploadFile_PassesBucketAndObject(t *testing.T) {
	dir := t.TempDir()
	srcPath := filepath.Join(dir, "f")
	_ = os.WriteFile(srcPath, []byte("x"), 0o644)

	wc := &stubWriteCloser{}
	w := &stubWriter{wc: wc}
	ul := storage.NewUploader(w)

	_ = ul.UploadFile(context.Background(), "hls-bucket", "videos/abc/index.m3u8", srcPath)

	if wc.calledBucket != "hls-bucket" {
		t.Errorf("bucket = %q, want %q", wc.calledBucket, "hls-bucket")
	}
	if wc.calledObject != "videos/abc/index.m3u8" {
		t.Errorf("object = %q, want %q", wc.calledObject, "videos/abc/index.m3u8")
	}
}

func TestUploader_UploadFile_MissingSrcFile(t *testing.T) {
	wc := &stubWriteCloser{}
	w := &stubWriter{wc: wc}
	ul := storage.NewUploader(w)

	err := ul.UploadFile(context.Background(), "b", "o", "/nonexistent/path.mp4")
	if err == nil {
		t.Fatal("expected error for missing src file")
	}
}

func TestUploader_UploadFile_CloseError(t *testing.T) {
	dir := t.TempDir()
	srcPath := filepath.Join(dir, "f")
	_ = os.WriteFile(srcPath, []byte("data"), 0o644)

	wc := &stubWriteCloser{closeErr: errors.New("finalise error")}
	w := &stubWriter{wc: wc}
	ul := storage.NewUploader(w)

	err := ul.UploadFile(context.Background(), "b", "o", srcPath)
	if err == nil {
		t.Fatal("expected close error")
	}
}

func TestUploader_UploadDir_UploadsAllFiles(t *testing.T) {
	dir := t.TempDir()
	// Create a small directory tree.
	_ = os.WriteFile(filepath.Join(dir, "index.m3u8"), []byte("master"), 0o644)
	_ = os.MkdirAll(filepath.Join(dir, "sub"), 0o755)
	_ = os.WriteFile(filepath.Join(dir, "sub", "0.ts"), []byte("segment"), 0o644)

	var uploaded []string
	var writers []*stubWriteCloser

	w := &stubWriterMulti{
		onCreate: func(bucket, object string) io.WriteCloser {
			wc := &stubWriteCloser{}
			wc.calledBucket = bucket
			wc.calledObject = object
			uploaded = append(uploaded, object)
			writers = append(writers, wc)
			return wc
		},
	}
	ul := storage.NewUploader(w)

	if err := ul.UploadDir(context.Background(), "hls-bucket", "videos/id123", dir); err != nil {
		t.Fatalf("unexpected error: %v", err)
	}

	if len(uploaded) != 2 {
		t.Fatalf("expected 2 uploaded files, got %d: %v", len(uploaded), uploaded)
	}
	for _, obj := range uploaded {
		if !strings.HasPrefix(obj, "videos/id123/") {
			t.Errorf("object %q missing prefix videos/id123/", obj)
		}
	}
}

// stubWriterMulti allows per-call customisation.
type stubWriterMulti struct {
	onCreate func(bucket, object string) io.WriteCloser
}

func (s *stubWriterMulti) NewWriter(_ context.Context, bucket, object string) io.WriteCloser {
	return s.onCreate(bucket, object)
}

func TestUploader_UploadDir_EmptyDir(t *testing.T) {
	dir := t.TempDir()
	w := &stubWriterMulti{
		onCreate: func(_, _ string) io.WriteCloser { return &stubWriteCloser{} },
	}
	ul := storage.NewUploader(w)

	// An empty dir should succeed with zero uploads.
	if err := ul.UploadDir(context.Background(), "b", "prefix", dir); err != nil {
		t.Fatalf("unexpected error on empty dir: %v", err)
	}
}

// ── read error during io.Copy ─────────────────────────────────────────────────

type errorReader struct{}

func (errorReader) Read(_ []byte) (int, error) { return 0, errors.New("read error") }
func (errorReader) Close() error               { return nil }

type errorOpenReader struct{}

func (s *errorOpenReader) NewReader(_ context.Context, _, _ string) (io.ReadCloser, error) {
	return errorReader{}, nil
}

func TestDownloader_Download_CopyError(t *testing.T) {
	dir := t.TempDir()
	dl := storage.NewDownloader(&errorOpenReader{})

	err := dl.Download(context.Background(), "b", "o", filepath.Join(dir, "out"))
	if err == nil {
		t.Fatal("expected error from copy, got nil")
	}
}

// ── write error during io.Copy in UploadFile ──────────────────────────────────

type errorWriteCloser struct{}

func (errorWriteCloser) Write(_ []byte) (int, error) { return 0, errors.New("write error") }
func (errorWriteCloser) Close() error                { return nil }

type errorWriterStub struct{}

func (s *errorWriterStub) NewWriter(_ context.Context, _, _ string) io.WriteCloser {
	return errorWriteCloser{}
}

func TestUploader_UploadFile_WriteError(t *testing.T) {
	dir := t.TempDir()
	srcPath := filepath.Join(dir, "src")
	_ = os.WriteFile(srcPath, []byte("data"), 0o644)

	ul := storage.NewUploader(&errorWriterStub{})
	err := ul.UploadFile(context.Background(), "b", "o", srcPath)
	if err == nil {
		t.Fatal("expected error from write, got nil")
	}
}
