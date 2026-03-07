// Package storage provides GCS download and upload helpers for the transcoder job.
package storage

import (
	"context"
	"fmt"
	"io"
	"os"
	"path/filepath"
)

// WriteAttrs holds optional metadata applied when creating a GCS object.
type WriteAttrs struct {
	CacheControl string
	ContentType  string
}

// attrsForPath returns appropriate WriteAttrs for a given file path based on its extension.
func attrsForPath(p string) WriteAttrs {
	switch filepath.Ext(p) {
	case ".m3u8":
		return WriteAttrs{
			ContentType:  "application/x-mpegurl",
			CacheControl: "no-cache, no-store, max-age=0",
		}
	case ".ts":
		return WriteAttrs{
			ContentType:  "video/mp2t",
			CacheControl: "public, max-age=31536000",
		}
	case ".jpg", ".jpeg":
		return WriteAttrs{
			ContentType:  "image/jpeg",
			CacheControl: "public, max-age=3600",
		}
	default:
		return WriteAttrs{}
	}
}

// ObjectReader abstracts GCS object reads so tests can inject a stub.
type ObjectReader interface {
	// NewReader opens a reader for the given bucket/object.
	NewReader(ctx context.Context, bucket, object string) (io.ReadCloser, error)
}

// ObjectWriter abstracts GCS object writes so tests can inject a stub.
type ObjectWriter interface {
	// NewWriter opens a writer for the given bucket/object with optional metadata attrs.
	// The caller must close the writer to finalise the upload.
	NewWriter(ctx context.Context, bucket, object string, attrs WriteAttrs) io.WriteCloser
}

// PrefixDeleter abstracts GCS prefix deletion so tests can inject a stub.
// Used by the transcoder to clean up partial HLS output on permanent failure.
type PrefixDeleter interface {
	// DeletePrefix deletes all objects in bucket whose name starts with prefix.
	DeletePrefix(ctx context.Context, bucket, prefix string) error
}

// Downloader downloads a raw GCS object to the local filesystem.
type Downloader struct {
	Reader ObjectReader
}

// NewDownloader constructs a Downloader backed by the provided ObjectReader.
func NewDownloader(r ObjectReader) *Downloader {
	return &Downloader{Reader: r}
}

// Download copies the GCS object at gs://<bucket>/<objectPath> to destPath.
// It creates any parent directories required.
func (d *Downloader) Download(ctx context.Context, bucket, objectPath, destPath string) error {
	if err := os.MkdirAll(filepath.Dir(destPath), 0o755); err != nil {
		return fmt.Errorf("mkdir %s: %w", filepath.Dir(destPath), err)
	}

	rc, err := d.Reader.NewReader(ctx, bucket, objectPath)
	if err != nil {
		return fmt.Errorf("open GCS reader gs://%s/%s: %w", bucket, objectPath, err)
	}
	defer rc.Close()

	f, err := os.Create(destPath)
	if err != nil {
		return fmt.Errorf("create local file %s: %w", destPath, err)
	}
	defer f.Close()

	if _, err := io.Copy(f, rc); err != nil {
		return fmt.Errorf("copy gs://%s/%s to %s: %w", bucket, objectPath, destPath, err)
	}
	return nil
}

// Uploader uploads local files to GCS.
type Uploader struct {
	Writer ObjectWriter
}

// NewUploader constructs an Uploader backed by the provided ObjectWriter.
func NewUploader(w ObjectWriter) *Uploader {
	return &Uploader{Writer: w}
}

// UploadFile copies a local file at srcPath to gs://<bucket>/<objectPath>.
// Content-Type and Cache-Control are set automatically based on the file extension.
func (u *Uploader) UploadFile(ctx context.Context, bucket, objectPath, srcPath string) error {
	f, err := os.Open(srcPath)
	if err != nil {
		return fmt.Errorf("open local file %s: %w", srcPath, err)
	}
	defer f.Close()

	wc := u.Writer.NewWriter(ctx, bucket, objectPath, attrsForPath(srcPath))
	if _, err := io.Copy(wc, f); err != nil {
		_ = wc.Close()
		return fmt.Errorf("copy %s to gs://%s/%s: %w", srcPath, bucket, objectPath, err)
	}
	if err := wc.Close(); err != nil {
		return fmt.Errorf("finalise upload gs://%s/%s: %w", bucket, objectPath, err)
	}
	return nil
}

// UploadDir walks srcDir and uploads every file to gs://<bucket>/<prefix>/<relPath>.
func (u *Uploader) UploadDir(ctx context.Context, bucket, prefix, srcDir string) error {
	return filepath.Walk(srcDir, func(path string, info os.FileInfo, err error) error {
		if err != nil {
			return err
		}
		if info.IsDir() {
			return nil
		}
		rel, err := filepath.Rel(srcDir, path)
		if err != nil {
			return fmt.Errorf("rel path for %s: %w", path, err)
		}
		objectPath := prefix + "/" + rel
		return u.UploadFile(ctx, bucket, objectPath, path)
	})
}
