package event_test

import (
	"strings"
	"testing"

	"github.com/ai-teammate/mytube/infra/transcoder-trigger/internal/event"
)

// ── VideoID ───────────────────────────────────────────────────────────────────

func TestVideoID_Standard(t *testing.T) {
	obj := event.StorageObject{Name: "raw/abc123.mp4"}
	id, err := obj.VideoID()
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if id != "abc123" {
		t.Errorf("expected abc123, got %q", id)
	}
}

func TestVideoID_UUID(t *testing.T) {
	obj := event.StorageObject{Name: "raw/550e8400-e29b-41d4-a716-446655440000.mp4"}
	id, err := obj.VideoID()
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if id != "550e8400-e29b-41d4-a716-446655440000" {
		t.Errorf("unexpected id: %q", id)
	}
}

func TestVideoID_NoExtension(t *testing.T) {
	obj := event.StorageObject{Name: "raw/abc123"}
	id, err := obj.VideoID()
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if id != "abc123" {
		t.Errorf("expected abc123, got %q", id)
	}
}

func TestVideoID_EmptyName(t *testing.T) {
	obj := event.StorageObject{Name: ""}
	_, err := obj.VideoID()
	if err == nil {
		t.Fatal("expected error for empty name, got nil")
	}
}

func TestVideoID_DotName(t *testing.T) {
	obj := event.StorageObject{Name: "."}
	_, err := obj.VideoID()
	if err == nil {
		t.Fatal("expected error for '.' name, got nil")
	}
}

func TestVideoID_OnlyExtension(t *testing.T) {
	obj := event.StorageObject{Name: "raw/.mp4"}
	_, err := obj.VideoID()
	if err == nil {
		t.Fatal("expected error when base is only an extension, got nil")
	}
}

// ── Parse ─────────────────────────────────────────────────────────────────────

func TestParse_Valid(t *testing.T) {
	body := `{"bucket":"mytube-raw-uploads","name":"raw/abc.mp4"}`
	obj, err := event.Parse(strings.NewReader(body))
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if obj.Bucket != "mytube-raw-uploads" {
		t.Errorf("unexpected bucket: %q", obj.Bucket)
	}
	if obj.Name != "raw/abc.mp4" {
		t.Errorf("unexpected name: %q", obj.Name)
	}
}

func TestParse_MissingBucket(t *testing.T) {
	body := `{"name":"raw/abc.mp4"}`
	_, err := event.Parse(strings.NewReader(body))
	if err == nil {
		t.Fatal("expected error for missing bucket, got nil")
	}
}

func TestParse_MissingName(t *testing.T) {
	body := `{"bucket":"mytube-raw-uploads"}`
	_, err := event.Parse(strings.NewReader(body))
	if err == nil {
		t.Fatal("expected error for missing name, got nil")
	}
}

func TestParse_InvalidJSON(t *testing.T) {
	_, err := event.Parse(strings.NewReader("not-json"))
	if err == nil {
		t.Fatal("expected error for invalid JSON, got nil")
	}
}

func TestParse_Empty(t *testing.T) {
	_, err := event.Parse(strings.NewReader(""))
	if err == nil {
		t.Fatal("expected error for empty body, got nil")
	}
}

// ── IsRawUpload ───────────────────────────────────────────────────────────────

func TestIsRawUpload_ValidMp4(t *testing.T) {
	obj := event.StorageObject{Bucket: "mytube-raw-uploads", Name: "raw/abc123.mp4"}
	if !obj.IsRawUpload() {
		t.Error("expected IsRawUpload() == true for raw/abc123.mp4")
	}
}

func TestIsRawUpload_ValidUUIDMp4(t *testing.T) {
	obj := event.StorageObject{
		Bucket: "mytube-raw-uploads",
		Name:   "raw/550e8400-e29b-41d4-a716-446655440000.mp4",
	}
	if !obj.IsRawUpload() {
		t.Error("expected IsRawUpload() == true for UUID-named mp4")
	}
}

func TestIsRawUpload_NonRawPrefix(t *testing.T) {
	obj := event.StorageObject{Bucket: "mytube-raw-uploads", Name: "thumbnails/poster.jpg"}
	if obj.IsRawUpload() {
		t.Error("expected IsRawUpload() == false for non-raw/ prefix")
	}
}

func TestIsRawUpload_ValidUUIDNoExtension(t *testing.T) {
	// Production uploads are stored without a file extension: raw/<userID>/<videoID>
	obj := event.StorageObject{
		Bucket: "mytube-raw-uploads",
		Name:   "raw/a4d86461-b30a-4edb-8de7-271b2839fa76/ca21d36d-ff29-414b-8e45-8f74d1fc509c",
	}
	if !obj.IsRawUpload() {
		t.Error("expected IsRawUpload() == true for production UUID path without extension")
	}
}

func TestIsRawUpload_RootLevelFile(t *testing.T) {
	obj := event.StorageObject{Bucket: "mytube-raw-uploads", Name: "video.mp4"}
	if obj.IsRawUpload() {
		t.Error("expected IsRawUpload() == false for root-level file (no raw/ prefix)")
	}
}

func TestIsRawUpload_EmptyName(t *testing.T) {
	obj := event.StorageObject{Bucket: "mytube-raw-uploads", Name: ""}
	if obj.IsRawUpload() {
		t.Error("expected IsRawUpload() == false for empty name")
	}
}
