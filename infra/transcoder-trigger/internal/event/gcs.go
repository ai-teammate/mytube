// Package event parses CloudEvent payloads sent by Eventarc for GCS object
// finalization events.
package event

import (
	"encoding/json"
	"fmt"
	"io"
	"path"
	"strings"
)

// StorageObject holds the subset of GCS object metadata that the trigger
// needs from an Eventarc google.cloud.storage.object.v1.finalized payload.
type StorageObject struct {
	// Bucket is the GCS bucket name (e.g. "mytube-raw-uploads").
	Bucket string `json:"bucket"`
	// Name is the GCS object path (e.g. "raw/<uuid>.mp4").
	Name string `json:"name"`
}

// VideoID extracts the video UUID from the object name.
// Expected naming convention: "raw/<uuid>.<ext>" (see MYTUBE-42 Option A).
// The UUID is the base name of the path with the extension stripped.
func (o StorageObject) VideoID() (string, error) {
	base := path.Base(o.Name)
	if base == "" || base == "." {
		return "", fmt.Errorf("object name %q has no base component", o.Name)
	}
	// Strip extension.
	ext := path.Ext(base)
	id := strings.TrimSuffix(base, ext)
	if id == "" {
		return "", fmt.Errorf("could not derive video ID from object name %q", o.Name)
	}
	return id, nil
}

// Parse decodes a JSON-encoded GCS StorageObject from r.
func Parse(r io.Reader) (StorageObject, error) {
	var obj StorageObject
	if err := json.NewDecoder(r).Decode(&obj); err != nil {
		return StorageObject{}, fmt.Errorf("decode storage object: %w", err)
	}
	if obj.Bucket == "" {
		return StorageObject{}, fmt.Errorf("storage object missing bucket")
	}
	if obj.Name == "" {
		return StorageObject{}, fmt.Errorf("storage object missing name")
	}
	return obj, nil
}
