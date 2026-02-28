// Package ffmpeg wraps the FFmpeg binary for HLS transcoding and thumbnail extraction.
package ffmpeg

import (
	"context"
	"fmt"
	"os/exec"
)

// Rendition describes a single HLS output stream.
type Rendition struct {
	// Name is used as the variant playlist filename (e.g. "360p").
	Name string
	// Height is the video height in pixels (e.g. 360).
	Height int
	// VideoBitrate is the target video bitrate string (e.g. "500k").
	VideoBitrate string
	// AudioBitrate is the target audio bitrate string (e.g. "64k").
	AudioBitrate string
}

// DefaultRenditions returns the three required HLS renditions.
func DefaultRenditions() []Rendition {
	return []Rendition{
		{Name: "360p", Height: 360, VideoBitrate: "500k", AudioBitrate: "64k"},
		{Name: "720p", Height: 720, VideoBitrate: "1500k", AudioBitrate: "128k"},
		{Name: "1080p", Height: 1080, VideoBitrate: "3000k", AudioBitrate: "192k"},
	}
}

// CommandRunner abstracts exec.CommandContext so tests can inject a stub.
type CommandRunner interface {
	// Run executes name with args and returns any error.
	Run(ctx context.Context, name string, args ...string) error
}

// ExecCommandRunner is the real CommandRunner that shells out to the system.
type ExecCommandRunner struct{}

// Run executes name with args using os/exec.
func (ExecCommandRunner) Run(ctx context.Context, name string, args ...string) error {
	cmd := exec.CommandContext(ctx, name, args...)
	out, err := cmd.CombinedOutput()
	if err != nil {
		return fmt.Errorf("ffmpeg exited with error: %w\noutput:\n%s", err, string(out))
	}
	return nil
}

// Runner wraps FFmpeg commands for HLS transcoding and thumbnail extraction.
type Runner struct {
	// Cmd is the command executor; defaults to ExecCommandRunner{}.
	Cmd CommandRunner
}

// NewRunner constructs a Runner with the real ExecCommandRunner.
func NewRunner() *Runner {
	return &Runner{Cmd: ExecCommandRunner{}}
}

// TranscodeHLS runs FFmpeg to produce an adaptive HLS output from inputPath.
// outputDir must exist; FFmpeg writes the master playlist as index.m3u8 and
// variant playlists + segments under outputDir.
func (r *Runner) TranscodeHLS(ctx context.Context, inputPath, outputDir string, renditions []Rendition) error {
	if len(renditions) == 0 {
		return fmt.Errorf("at least one rendition is required")
	}

	args := []string{"-y", "-i", inputPath}

	// Build one output stream per rendition.
	for i, rend := range renditions {
		args = append(args,
			"-map", "0:v:0",
			"-map", "0:a:0",
			fmt.Sprintf("-c:v:%d", i), "libx264",
			fmt.Sprintf("-b:v:%d", i), rend.VideoBitrate,
			fmt.Sprintf("-vf:v:%d", i), fmt.Sprintf("scale=-2:%d", rend.Height),
			fmt.Sprintf("-c:a:%d", i), "aac",
			fmt.Sprintf("-b:a:%d", i), rend.AudioBitrate,
		)
	}

	// HLS muxer settings.
	args = append(args,
		"-f", "hls",
		"-hls_time", "6",
		"-hls_playlist_type", "vod",
		"-hls_flags", "independent_segments",
		"-hls_segment_type", "mpegts",
		"-hls_segment_filename", outputDir+"/%v_%03d.ts",
		"-master_pl_name", "index.m3u8",
		"-var_stream_map", buildStreamMap(renditions),
		outputDir+"/%v.m3u8",
	)

	return r.Cmd.Run(ctx, "ffmpeg", args...)
}

// ExtractThumbnail extracts a single frame at offset seconds from inputPath
// and writes it as a JPEG to destPath.
func (r *Runner) ExtractThumbnail(ctx context.Context, inputPath, destPath string, offsetSeconds int) error {
	args := []string{
		"-y",
		"-ss", fmt.Sprintf("%d", offsetSeconds),
		"-i", inputPath,
		"-frames:v", "1",
		"-q:v", "2",
		destPath,
	}
	return r.Cmd.Run(ctx, "ffmpeg", args...)
}

// buildStreamMap produces the -var_stream_map value, e.g.:
// "v:0,a:0 v:1,a:1 v:2,a:2"
func buildStreamMap(renditions []Rendition) string {
	result := ""
	for i := range renditions {
		if i > 0 {
			result += " "
		}
		result += fmt.Sprintf("v:%d,a:%d,name:%s", i, i, renditions[i].Name)
	}
	return result
}
