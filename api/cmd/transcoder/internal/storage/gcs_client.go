package storage

import (
	"context"
	"fmt"
	"io"

	"cloud.google.com/go/storage"
	"google.golang.org/api/iterator"
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

// NewWriter opens a GCS object writer for bucket/object with the given metadata attrs.
func (g *GCSObjectWriter) NewWriter(ctx context.Context, bucket, object string, attrs WriteAttrs) io.WriteCloser {
	wc := g.client.Bucket(bucket).Object(object).NewWriter(ctx)
	if attrs.CacheControl != "" {
		wc.CacheControl = attrs.CacheControl
	}
	if attrs.ContentType != "" {
		wc.ContentType = attrs.ContentType
	}
	return wc
}

// GCSPrefixDeleter implements PrefixDeleter using the real GCS client.
type GCSPrefixDeleter struct {
	client *storage.Client
}

// NewGCSPrefixDeleter wraps a *storage.Client as a PrefixDeleter.
func NewGCSPrefixDeleter(client *storage.Client) *GCSPrefixDeleter {
	return &GCSPrefixDeleter{client: client}
}

// DeletePrefix deletes all GCS objects whose name starts with prefix in bucket.
// Not-found errors on individual objects are silently ignored.
func (g *GCSPrefixDeleter) DeletePrefix(ctx context.Context, bucket, prefix string) error {
	it := g.client.Bucket(bucket).Objects(ctx, &storage.Query{Prefix: prefix})
	for {
		attrs, err := it.Next()
		if err == iterator.Done {
			break
		}
		if err != nil {
			return fmt.Errorf("list objects under gs://%s/%s: %w", bucket, prefix, err)
		}
		if delErr := g.client.Bucket(bucket).Object(attrs.Name).Delete(ctx); delErr != nil && delErr != storage.ErrObjectNotExist {
			return fmt.Errorf("delete gs://%s/%s: %w", bucket, attrs.Name, delErr)
		}
	}
	return nil
}
