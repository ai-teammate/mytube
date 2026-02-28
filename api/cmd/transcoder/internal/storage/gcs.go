// Package storage provides GCS download and upload helpers for the transcoder job.
package storage

import (
	"context"
	"fmt"
	"io"
	"os"
	"path/filepath"
)

// ObjectReader abstracts GCS object reads so tests can inject a stub.
type ObjectReader interface {
	// NewReader opens a reader for the given bucket/object.
	NewReader(ctx context.Context, bucket, object string) (io.ReadCloser, error)
}

// ObjectWriter abstracts GCS object writes so tests can inject a stub.
type ObjectWriter interface {
	// NewWriter opens a writer for the given bucket/object.
	// The caller must close the writer to finalise the upload.
	NewWriter(ctx context.Context, bucket, object string) io.WriteCloser
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
func (u *Uploader) UploadFile(ctx context.Context, bucket, objectPath, srcPath string) error {
	f, err := os.Open(srcPath)
	if err != nil {
		return fmt.Errorf("open local file %s: %w", srcPath, err)
	}
	defer f.Close()

	wc := u.Writer.NewWriter(ctx, bucket, objectPath)
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
