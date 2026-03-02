package storage

import (
	"context"
	"io"

	"cloud.google.com/go/storage"
)

// GCSObjectReader implements ObjectReader using the real GCS client.
type GCSObjectReader struct {
	client *storage.Client
}

// NewGCSObjectReader wraps a *storage.Client as an ObjectReader.
func NewGCSObjectReader(client *storage.Client) *GCSObjectReader {
	return &GCSObjectReader{client: client}
}

// NewReader opens a GCS object reader for bucket/object.
func (g *GCSObjectReader) NewReader(ctx context.Context, bucket, object string) (io.ReadCloser, error) {
	return g.client.Bucket(bucket).Object(object).NewReader(ctx)
}

// GCSObjectWriter implements ObjectWriter using the real GCS client.
type GCSObjectWriter struct {
	client *storage.Client
}

// NewGCSObjectWriter wraps a *storage.Client as an ObjectWriter.
func NewGCSObjectWriter(client *storage.Client) *GCSObjectWriter {
	return &GCSObjectWriter{client: client}
}

// NewWriter opens a GCS object writer for bucket/object.
func (g *GCSObjectWriter) NewWriter(ctx context.Context, bucket, object string) io.WriteCloser {
	return g.client.Bucket(bucket).Object(object).NewWriter(ctx)
}
