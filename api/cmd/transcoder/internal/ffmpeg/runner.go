// Package ffmpeg wraps the FFmpeg binary for HLS transcoding and thumbnail extraction.
package ffmpeg

import (
	"context"
	"fmt"
	"log"
	"os/exec"
	"regexp"
	"strings"
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

// ProbeRunner abstracts output-capturing command execution used for stream detection.
type ProbeRunner interface {
	// Output executes name with args and returns the combined stdout+stderr output.
	// Non-zero exit codes are not treated as errors — callers inspect the output.
	Output(ctx context.Context, name string, args ...string) []byte
}

// ExecProbeRunner is the real ProbeRunner that shells out to the system.
type ExecProbeRunner struct{}

// Output runs the command and returns combined stdout+stderr regardless of exit code.
func (ExecProbeRunner) Output(ctx context.Context, name string, args ...string) []byte {
	cmd := exec.CommandContext(ctx, name, args...)
	out, _ := cmd.CombinedOutput()
	return out
}

// Runner wraps FFmpeg commands for HLS transcoding and thumbnail extraction.
type Runner struct {
	// Cmd is the command executor; defaults to ExecCommandRunner{}.
	Cmd CommandRunner
	// Probe is the output-capturing runner used for stream probing; defaults to ExecProbeRunner{}.
	Probe ProbeRunner
}

// NewRunner constructs a Runner with the real ExecCommandRunner and ExecProbeRunner.
func NewRunner() *Runner {
	return &Runner{Cmd: ExecCommandRunner{}, Probe: ExecProbeRunner{}}
}

// HasAudioStream reports whether the media file at inputPath contains at least one
// audio stream. It uses ffprobe (bundled with the ffmpeg Alpine package) to query
// stream metadata; falls back to parsing ffmpeg -i stderr when ffprobe is unavailable.
// Probing is best-effort: if both probes return empty output the function returns false
// (video-only assumption) and logs a warning. When no audio stream is present, FFmpeg
// audio-mapping flags must be omitted to avoid a fatal "Invalid argument" error.
func (r *Runner) HasAudioStream(ctx context.Context, inputPath string) bool {
	probe := r.Probe
	if probe == nil {
		probe = ExecProbeRunner{}
	}
	// ffprobe -select_streams a lists only audio streams; empty output means none.
	out := probe.Output(ctx, "ffprobe",
		"-v", "error",
		"-select_streams", "a",
		"-show_entries", "stream=codec_type",
		"-of", "csv=p=0",
		inputPath,
	)
	if strings.TrimSpace(string(out)) != "" {
		return true
	}
	// Fallback: parse ffmpeg -i stderr (ffmpeg always exits non-zero here).
	out2 := probe.Output(ctx, "ffmpeg", "-hide_banner", "-i", inputPath)
	if len(out2) == 0 {
		log.Printf("audio probe returned no output for %q: assuming video-only", inputPath)
	}
	return strings.Contains(string(out2), "Audio:")
}

// TranscodeHLS runs FFmpeg to produce an adaptive HLS output from inputPath.
// outputDir must exist; FFmpeg writes the master playlist as index.m3u8 and
// variant playlists + segments under outputDir.
// Videos with no audio stream are transcoded successfully — audio mapping flags
// are omitted when no audio stream is detected.
func (r *Runner) TranscodeHLS(ctx context.Context, inputPath, outputDir string, renditions []Rendition) error {
	if len(renditions) == 0 {
		return fmt.Errorf("at least one rendition is required")
	}

	hasAudio := r.HasAudioStream(ctx, inputPath)
	if !hasAudio {
		log.Printf("no audio stream detected in %s — transcoding video-only (audio mapping skipped)", inputPath)
	}

	args := []string{"-y", "-i", inputPath}

	// Build one output stream per rendition.
	for i, rend := range renditions {
		args = append(args,
			"-map", "0:v:0",
		)
		if hasAudio {
			args = append(args, "-map", "0:a:0")
		}
		args = append(args,
			fmt.Sprintf("-c:v:%d", i), "libx264",
			fmt.Sprintf("-b:v:%d", i), rend.VideoBitrate,
			fmt.Sprintf("-vf:v:%d", i), fmt.Sprintf("scale=-2:%d", rend.Height),
		)
		if hasAudio {
			args = append(args,
				fmt.Sprintf("-c:a:%d", i), "aac",
				fmt.Sprintf("-b:a:%d", i), rend.AudioBitrate,
			)
		}
	}

	streamMap, err := buildStreamMap(renditions, hasAudio)
	if err != nil {
		return fmt.Errorf("build stream map: %w", err)
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
		"-var_stream_map", streamMap,
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

// nameRe restricts rendition names to alphanumeric characters, hyphens, and
// underscores, preventing argument injection into the FFmpeg -var_stream_map flag.
var nameRe = regexp.MustCompile(`^[a-zA-Z0-9_-]+$`)

// buildStreamMap produces the -var_stream_map value.
// With audio:    "v:0,a:0,name:360p v:1,a:1,name:720p v:2,a:2,name:1080p"
// Without audio: "v:0,name:360p v:1,name:720p v:2,name:1080p"
// It returns an error if any rendition name contains characters outside [a-zA-Z0-9_-].
func buildStreamMap(renditions []Rendition, hasAudio bool) (string, error) {
	var b strings.Builder
	for i, rend := range renditions {
		if !nameRe.MatchString(rend.Name) {
			return "", fmt.Errorf("invalid rendition name %q: must match [a-zA-Z0-9_-]+", rend.Name)
		}
		if i > 0 {
			b.WriteString(" ")
		}
		if hasAudio {
			fmt.Fprintf(&b, "v:%d,a:%d,name:%s", i, i, rend.Name)
		} else {
			fmt.Fprintf(&b, "v:%d,name:%s", i, rend.Name)
		}
	}
	return b.String(), nil
}
