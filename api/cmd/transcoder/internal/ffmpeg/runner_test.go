package ffmpeg_test

import (
	"context"
	"errors"
	"strings"
	"testing"

	"github.com/ai-teammate/mytube/api/cmd/transcoder/internal/ffmpeg"
)

// ── stub CommandRunner ─────────────────────────────────────────────────────────

type stubRunner struct {
	err       error
	calls     []call
}

type call struct {
	name string
	args []string
}

func (s *stubRunner) Run(_ context.Context, name string, args ...string) error {
	s.calls = append(s.calls, call{name: name, args: args})
	return s.err
}

// ── DefaultRenditions ─────────────────────────────────────────────────────────

func TestDefaultRenditions_Count(t *testing.T) {
	r := ffmpeg.DefaultRenditions()
	if len(r) != 3 {
		t.Errorf("expected 3 renditions, got %d", len(r))
	}
}

func TestDefaultRenditions_Names(t *testing.T) {
	r := ffmpeg.DefaultRenditions()
	want := []string{"360p", "720p", "1080p"}
	for i, rend := range r {
		if rend.Name != want[i] {
			t.Errorf("rendition[%d].Name = %q, want %q", i, rend.Name, want[i])
		}
	}
}

func TestDefaultRenditions_Bitrates(t *testing.T) {
	r := ffmpeg.DefaultRenditions()
	bitrates := []string{"500k", "1500k", "3000k"}
	for i, rend := range r {
		if rend.VideoBitrate != bitrates[i] {
			t.Errorf("rendition[%d].VideoBitrate = %q, want %q", i, rend.VideoBitrate, bitrates[i])
		}
	}
}

func TestDefaultRenditions_Heights(t *testing.T) {
	r := ffmpeg.DefaultRenditions()
	heights := []int{360, 720, 1080}
	for i, rend := range r {
		if rend.Height != heights[i] {
			t.Errorf("rendition[%d].Height = %d, want %d", i, rend.Height, heights[i])
		}
	}
}

// ── NewRunner ─────────────────────────────────────────────────────────────────

func TestNewRunner_NotNil(t *testing.T) {
	r := ffmpeg.NewRunner()
	if r == nil {
		t.Fatal("NewRunner() returned nil")
	}
}

// ── TranscodeHLS ──────────────────────────────────────────────────────────────

func TestTranscodeHLS_CallsFFmpeg(t *testing.T) {
	stub := &stubRunner{}
	r := &ffmpeg.Runner{Cmd: stub}

	err := r.TranscodeHLS(context.Background(), "input.mp4", "/out", ffmpeg.DefaultRenditions())
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if len(stub.calls) != 1 {
		t.Fatalf("expected 1 FFmpeg call, got %d", len(stub.calls))
	}
	if stub.calls[0].name != "ffmpeg" {
		t.Errorf("command name = %q, want ffmpeg", stub.calls[0].name)
	}
}

func TestTranscodeHLS_ArgsContainInputPath(t *testing.T) {
	stub := &stubRunner{}
	r := &ffmpeg.Runner{Cmd: stub}

	_ = r.TranscodeHLS(context.Background(), "/video/raw.mp4", "/hls", ffmpeg.DefaultRenditions())

	args := stub.calls[0].args
	found := false
	for _, a := range args {
		if a == "/video/raw.mp4" {
			found = true
			break
		}
	}
	if !found {
		t.Errorf("args do not contain input path: %v", args)
	}
}

func TestTranscodeHLS_ArgsContainOutputDir(t *testing.T) {
	stub := &stubRunner{}
	r := &ffmpeg.Runner{Cmd: stub}

	_ = r.TranscodeHLS(context.Background(), "in.mp4", "/hls/out", ffmpeg.DefaultRenditions())

	args := stub.calls[0].args
	found := false
	for _, a := range args {
		if strings.Contains(a, "/hls/out") {
			found = true
			break
		}
	}
	if !found {
		t.Errorf("args do not reference output dir: %v", args)
	}
}

func TestTranscodeHLS_ArgsContainMasterPlaylist(t *testing.T) {
	stub := &stubRunner{}
	r := &ffmpeg.Runner{Cmd: stub}

	_ = r.TranscodeHLS(context.Background(), "in.mp4", "/out", ffmpeg.DefaultRenditions())

	args := stub.calls[0].args
	found := false
	for _, a := range args {
		if a == "index.m3u8" {
			found = true
			break
		}
	}
	if !found {
		t.Errorf("args do not include master playlist name 'index.m3u8': %v", args)
	}
}

func TestTranscodeHLS_ArgsContainHLSFormat(t *testing.T) {
	stub := &stubRunner{}
	r := &ffmpeg.Runner{Cmd: stub}

	_ = r.TranscodeHLS(context.Background(), "in.mp4", "/out", ffmpeg.DefaultRenditions())

	args := stub.calls[0].args
	found := false
	for _, a := range args {
		if a == "hls" {
			found = true
			break
		}
	}
	if !found {
		t.Errorf("args do not contain '-f hls': %v", args)
	}
}

func TestTranscodeHLS_ArgsContainAllRenditionBitrates(t *testing.T) {
	stub := &stubRunner{}
	r := &ffmpeg.Runner{Cmd: stub}
	renditions := ffmpeg.DefaultRenditions()

	_ = r.TranscodeHLS(context.Background(), "in.mp4", "/out", renditions)

	argsStr := strings.Join(stub.calls[0].args, " ")
	for _, rend := range renditions {
		if !strings.Contains(argsStr, rend.VideoBitrate) {
			t.Errorf("args missing video bitrate %q: %s", rend.VideoBitrate, argsStr)
		}
	}
}

func TestTranscodeHLS_EmptyRenditions_ReturnsError(t *testing.T) {
	stub := &stubRunner{}
	r := &ffmpeg.Runner{Cmd: stub}

	err := r.TranscodeHLS(context.Background(), "in.mp4", "/out", nil)
	if err == nil {
		t.Fatal("expected error for empty renditions")
	}
	if len(stub.calls) != 0 {
		t.Error("FFmpeg must not be called when renditions is empty")
	}
}

func TestTranscodeHLS_FFmpegError_Propagated(t *testing.T) {
	stub := &stubRunner{err: errors.New("ffmpeg failed")}
	r := &ffmpeg.Runner{Cmd: stub}

	err := r.TranscodeHLS(context.Background(), "in.mp4", "/out", ffmpeg.DefaultRenditions())
	if err == nil {
		t.Fatal("expected error to be propagated")
	}
}

// ── ExtractThumbnail ──────────────────────────────────────────────────────────

func TestExtractThumbnail_CallsFFmpeg(t *testing.T) {
	stub := &stubRunner{}
	r := &ffmpeg.Runner{Cmd: stub}

	err := r.ExtractThumbnail(context.Background(), "input.mp4", "/out/thumbnail.jpg", 5)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if len(stub.calls) != 1 {
		t.Fatalf("expected 1 FFmpeg call, got %d", len(stub.calls))
	}
}

func TestExtractThumbnail_ArgsContainSSOffset(t *testing.T) {
	stub := &stubRunner{}
	r := &ffmpeg.Runner{Cmd: stub}

	_ = r.ExtractThumbnail(context.Background(), "in.mp4", "thumb.jpg", 5)

	args := stub.calls[0].args
	foundSS := false
	foundVal := false
	for i, a := range args {
		if a == "-ss" {
			foundSS = true
			if i+1 < len(args) && args[i+1] == "5" {
				foundVal = true
			}
		}
	}
	if !foundSS || !foundVal {
		t.Errorf("args missing '-ss 5': %v", args)
	}
}

func TestExtractThumbnail_ArgsContainFramesV1(t *testing.T) {
	stub := &stubRunner{}
	r := &ffmpeg.Runner{Cmd: stub}

	_ = r.ExtractThumbnail(context.Background(), "in.mp4", "thumb.jpg", 5)

	args := stub.calls[0].args
	found := false
	for i, a := range args {
		if a == "-frames:v" && i+1 < len(args) && args[i+1] == "1" {
			found = true
			break
		}
	}
	if !found {
		t.Errorf("args missing '-frames:v 1': %v", args)
	}
}

func TestExtractThumbnail_ArgsContainDestPath(t *testing.T) {
	stub := &stubRunner{}
	r := &ffmpeg.Runner{Cmd: stub}

	_ = r.ExtractThumbnail(context.Background(), "in.mp4", "/output/thumb.jpg", 5)

	args := stub.calls[0].args
	found := false
	for _, a := range args {
		if a == "/output/thumb.jpg" {
			found = true
			break
		}
	}
	if !found {
		t.Errorf("args missing dest path '/output/thumb.jpg': %v", args)
	}
}

func TestExtractThumbnail_ArgsContainInputPath(t *testing.T) {
	stub := &stubRunner{}
	r := &ffmpeg.Runner{Cmd: stub}

	_ = r.ExtractThumbnail(context.Background(), "/video/raw.mp4", "thumb.jpg", 0)

	args := stub.calls[0].args
	found := false
	for _, a := range args {
		if a == "/video/raw.mp4" {
			found = true
			break
		}
	}
	if !found {
		t.Errorf("args missing input path: %v", args)
	}
}

func TestExtractThumbnail_FFmpegError_Propagated(t *testing.T) {
	stub := &stubRunner{err: errors.New("ffmpeg exit 1")}
	r := &ffmpeg.Runner{Cmd: stub}

	err := r.ExtractThumbnail(context.Background(), "in.mp4", "thumb.jpg", 5)
	if err == nil {
		t.Fatal("expected error to be propagated")
	}
}

func TestExtractThumbnail_ZeroOffset(t *testing.T) {
	stub := &stubRunner{}
	r := &ffmpeg.Runner{Cmd: stub}

	if err := r.ExtractThumbnail(context.Background(), "in.mp4", "thumb.jpg", 0); err != nil {
		t.Fatalf("unexpected error with offset 0: %v", err)
	}
}

// ── ExecCommandRunner ─────────────────────────────────────────────────────────

func TestExecCommandRunner_SuccessCommand(t *testing.T) {
	runner := ffmpeg.ExecCommandRunner{}
	if err := runner.Run(context.Background(), "true"); err != nil {
		t.Fatalf("unexpected error running 'true': %v", err)
	}
}

func TestExecCommandRunner_FailingCommand(t *testing.T) {
	runner := ffmpeg.ExecCommandRunner{}
	if err := runner.Run(context.Background(), "false"); err == nil {
		t.Fatal("expected error running 'false', got nil")
	}
}

func TestExecCommandRunner_OutputCapturedInError(t *testing.T) {
	runner := ffmpeg.ExecCommandRunner{}
	err := runner.Run(context.Background(), "sh", "-c", "echo 'myerr' >&2; exit 1")
	if err == nil {
		t.Fatal("expected error")
	}
	if !strings.Contains(err.Error(), "myerr") {
		t.Errorf("expected error to contain command output, got: %v", err)
	}
}
