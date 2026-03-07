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
	err   error
	calls []call
}

type call struct {
	name string
	args []string
}

func (s *stubRunner) Run(_ context.Context, name string, args ...string) error {
	s.calls = append(s.calls, call{name: name, args: args})
	return s.err
}

// ── stub ProbeRunner ──────────────────────────────────────────────────────────

// stubProbeRunner simulates ffprobe/ffmpeg output for audio stream detection.
// It is name-aware: ffprobeOutput is returned for "ffprobe" calls and
// ffmpegOutput is returned for all other calls (e.g. "ffmpeg" fallback).
type stubProbeRunner struct {
	ffprobeOutput []byte
	ffmpegOutput  []byte
}

func (s *stubProbeRunner) Output(_ context.Context, name string, _ ...string) []byte {
	if name == "ffprobe" {
		return s.ffprobeOutput
	}
	return s.ffmpegOutput
}

// withAudio returns a ProbeRunner where ffprobe reports one audio stream present.
func withAudio() *stubProbeRunner {
	return &stubProbeRunner{ffprobeOutput: []byte("audio\n"), ffmpegOutput: []byte("")}
}

// withoutAudio returns a ProbeRunner that reports no audio streams on either probe.
func withoutAudio() *stubProbeRunner {
	return &stubProbeRunner{ffprobeOutput: []byte(""), ffmpegOutput: []byte("")}
}

// withAudioViaFallback returns a ProbeRunner where ffprobe returns empty (simulating
// ffprobe unavailable) but the ffmpeg fallback correctly detects an audio stream.
func withAudioViaFallback() *stubProbeRunner {
	return &stubProbeRunner{
		ffprobeOutput: []byte(""),
		ffmpegOutput:  []byte("Stream #0:1: Audio: aac"),
	}
}


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
	r := &ffmpeg.Runner{Cmd: stub, Probe: withAudio()}

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
	r := &ffmpeg.Runner{Cmd: stub, Probe: withAudio()}

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
	r := &ffmpeg.Runner{Cmd: stub, Probe: withAudio()}

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
	r := &ffmpeg.Runner{Cmd: stub, Probe: withAudio()}

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
	r := &ffmpeg.Runner{Cmd: stub, Probe: withAudio()}

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
	r := &ffmpeg.Runner{Cmd: stub, Probe: withAudio()}
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
	r := &ffmpeg.Runner{Cmd: stub, Probe: withAudio()}

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
	r := &ffmpeg.Runner{Cmd: stub, Probe: withAudio()}

	err := r.TranscodeHLS(context.Background(), "in.mp4", "/out", ffmpeg.DefaultRenditions())
	if err == nil {
		t.Fatal("expected error to be propagated")
	}
}

func TestTranscodeHLS_InvalidRenditionName_ReturnsError(t *testing.T) {
	stub := &stubRunner{}
	r := &ffmpeg.Runner{Cmd: stub, Probe: withAudio()}

	bad := []ffmpeg.Rendition{
		{Name: "bad name!", Height: 360, VideoBitrate: "500k", AudioBitrate: "64k"},
	}
	err := r.TranscodeHLS(context.Background(), "in.mp4", "/out", bad)
	if err == nil {
		t.Fatal("expected error for invalid rendition name")
	}
	if len(stub.calls) != 0 {
		t.Error("FFmpeg must not be called when rendition name is invalid")
	}
}

func TestTranscodeHLS_RenditionNameWithComma_ReturnsError(t *testing.T) {
	stub := &stubRunner{}
	r := &ffmpeg.Runner{Cmd: stub, Probe: withAudio()}

	bad := []ffmpeg.Rendition{
		{Name: "360p,bad", Height: 360, VideoBitrate: "500k", AudioBitrate: "64k"},
	}
	err := r.TranscodeHLS(context.Background(), "in.mp4", "/out", bad)
	if err == nil {
		t.Fatal("expected error for rendition name containing comma")
	}
}

// ── Silent-video (no audio stream) tests — regression for MYTUBE-359 ──────────

// TestTranscodeHLS_SilentVideo_NoAudioMapArgs verifies that when the input has no
// audio stream, the FFmpeg command does NOT include "-map 0:a:0" or any "-c:a"
// or "-b:a" flags. Before the fix this would cause FFmpeg to exit with
// "Failed to set value '0:a:0' for option 'map': Invalid argument".
func TestTranscodeHLS_SilentVideo_NoAudioMapArgs(t *testing.T) {
	stub := &stubRunner{}
	r := &ffmpeg.Runner{Cmd: stub, Probe: withoutAudio()}

	err := r.TranscodeHLS(context.Background(), "silent.mp4", "/out", ffmpeg.DefaultRenditions())
	if err != nil {
		t.Fatalf("silent video must not produce an error, got: %v", err)
	}

	argsStr := strings.Join(stub.calls[0].args, " ")
	if strings.Contains(argsStr, "0:a:0") {
		t.Errorf("args must not contain '0:a:0' for silent video, got: %s", argsStr)
	}
	if strings.Contains(argsStr, "-c:a") {
		t.Errorf("args must not contain '-c:a' for silent video, got: %s", argsStr)
	}
	if strings.Contains(argsStr, "-b:a") {
		t.Errorf("args must not contain '-b:a' for silent video, got: %s", argsStr)
	}
}

// TestTranscodeHLS_SilentVideo_StreamMapNoAudio verifies that the -var_stream_map
// value excludes audio stream references (e.g. "a:0") when there is no audio.
func TestTranscodeHLS_SilentVideo_StreamMapNoAudio(t *testing.T) {
	stub := &stubRunner{}
	r := &ffmpeg.Runner{Cmd: stub, Probe: withoutAudio()}

	_ = r.TranscodeHLS(context.Background(), "silent.mp4", "/out", ffmpeg.DefaultRenditions())

	args := stub.calls[0].args
	var streamMap string
	for i, a := range args {
		if a == "-var_stream_map" && i+1 < len(args) {
			streamMap = args[i+1]
			break
		}
	}
	if streamMap == "" {
		t.Fatal("-var_stream_map not found in FFmpeg args")
	}
	if strings.Contains(streamMap, ",a:") {
		t.Errorf("-var_stream_map must not contain audio entries for silent video, got: %q", streamMap)
	}
	// Verify video entries are still present.
	if !strings.Contains(streamMap, "v:0") {
		t.Errorf("-var_stream_map must still contain video entries, got: %q", streamMap)
	}
}

// TestTranscodeHLS_SilentVideo_VideoMapArgPresent verifies that -map 0:v:0 is still
// included for each rendition when the input is silent (video-only).
func TestTranscodeHLS_SilentVideo_VideoMapArgPresent(t *testing.T) {
	stub := &stubRunner{}
	r := &ffmpeg.Runner{Cmd: stub, Probe: withoutAudio()}

	_ = r.TranscodeHLS(context.Background(), "silent.mp4", "/out", ffmpeg.DefaultRenditions())

	args := stub.calls[0].args
	count := 0
	for _, a := range args {
		if a == "0:v:0" {
			count++
		}
	}
	if count != len(ffmpeg.DefaultRenditions()) {
		t.Errorf("expected %d '-map 0:v:0' entries (one per rendition), got %d",
			len(ffmpeg.DefaultRenditions()), count)
	}
}

// TestTranscodeHLS_WithAudio_AudioMapArgsPresent verifies that with audio the
// original behaviour is preserved: "-map 0:a:0", "-c:a:N", "-b:a:N" are included.
func TestTranscodeHLS_WithAudio_AudioMapArgsPresent(t *testing.T) {
	stub := &stubRunner{}
	r := &ffmpeg.Runner{Cmd: stub, Probe: withAudio()}

	_ = r.TranscodeHLS(context.Background(), "with_audio.mp4", "/out", ffmpeg.DefaultRenditions())

	argsStr := strings.Join(stub.calls[0].args, " ")
	if !strings.Contains(argsStr, "0:a:0") {
		t.Errorf("args must contain '0:a:0' for video with audio, got: %s", argsStr)
	}
	if !strings.Contains(argsStr, "-c:a:0") {
		t.Errorf("args must contain '-c:a:0' for video with audio, got: %s", argsStr)
	}
}

// TestTranscodeHLS_WithAudio_StreamMapHasAudio verifies that the -var_stream_map
// includes audio entries (a:N) when the input has an audio stream.
func TestTranscodeHLS_WithAudio_StreamMapHasAudio(t *testing.T) {
	stub := &stubRunner{}
	r := &ffmpeg.Runner{Cmd: stub, Probe: withAudio()}

	_ = r.TranscodeHLS(context.Background(), "with_audio.mp4", "/out", ffmpeg.DefaultRenditions())

	args := stub.calls[0].args
	var streamMap string
	for i, a := range args {
		if a == "-var_stream_map" && i+1 < len(args) {
			streamMap = args[i+1]
			break
		}
	}
	if !strings.Contains(streamMap, ",a:") {
		t.Errorf("-var_stream_map must contain audio entries for video with audio, got: %q", streamMap)
	}
}

// TestTranscodeHLS_FallbackAudioDetection verifies that when ffprobe returns empty
// output (simulating ffprobe unavailable) but the ffmpeg -i fallback contains
// "Audio:", HasAudioStream correctly returns true and audio mapping flags are present.
func TestTranscodeHLS_FallbackAudioDetection(t *testing.T) {
	stub := &stubRunner{}
	r := &ffmpeg.Runner{Cmd: stub, Probe: withAudioViaFallback()}

	err := r.TranscodeHLS(context.Background(), "with_audio.mp4", "/out", ffmpeg.DefaultRenditions())
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}

	argsStr := strings.Join(stub.calls[0].args, " ")
	if !strings.Contains(argsStr, "0:a:0") {
		t.Errorf("fallback detection: args must contain '0:a:0' when ffmpeg fallback detects audio, got: %s", argsStr)
	}
	if !strings.Contains(argsStr, "-c:a:0") {
		t.Errorf("fallback detection: args must contain '-c:a:0' when ffmpeg fallback detects audio, got: %s", argsStr)
	}
}

// ── ExtractThumbnail ──────────────────────────────────────────────────────────

func TestExtractThumbnail_CallsFFmpeg(t *testing.T) {
	stub := &stubRunner{}
	r := &ffmpeg.Runner{Cmd: stub, Probe: withAudio()}

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
	r := &ffmpeg.Runner{Cmd: stub, Probe: withAudio()}

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
	r := &ffmpeg.Runner{Cmd: stub, Probe: withAudio()}

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
	r := &ffmpeg.Runner{Cmd: stub, Probe: withAudio()}

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
	r := &ffmpeg.Runner{Cmd: stub, Probe: withAudio()}

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
	r := &ffmpeg.Runner{Cmd: stub, Probe: withAudio()}

	err := r.ExtractThumbnail(context.Background(), "in.mp4", "thumb.jpg", 5)
	if err == nil {
		t.Fatal("expected error to be propagated")
	}
}

func TestExtractThumbnail_ZeroOffset(t *testing.T) {
	stub := &stubRunner{}
	r := &ffmpeg.Runner{Cmd: stub, Probe: withAudio()}

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
