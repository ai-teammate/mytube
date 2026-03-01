// Package jobs provides an abstraction for executing a Cloud Run Job.
package jobs

import (
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"strings"
)

// Executor executes a Cloud Run Job for a given raw GCS object.
type Executor interface {
	Execute(ctx context.Context, req ExecuteRequest) error
}

// ExecuteRequest carries the per-execution environment variable overrides
// that the Cloud Run Job will receive.
type ExecuteRequest struct {
	// RawObjectPath is the full GCS object path (e.g. "raw/<uuid>.mp4").
	RawObjectPath string
	// VideoID is the UUID extracted from the object name.
	VideoID string
	// HLSBucket is the destination bucket for HLS output.
	HLSBucket string
}

// HTTPDoer abstracts http.Client.Do so that tests can inject a stub.
type HTTPDoer interface {
	Do(req *http.Request) (*http.Response, error)
}

// CloudRunJobRunner calls the Cloud Run Jobs API over HTTP to execute a job.
// It uses the metadata server token (Application Default Credentials) when
// running inside Cloud Run.
type CloudRunJobRunner struct {
	Project string
	Region  string
	JobName string
	Client  HTTPDoer
}

// NewCloudRunJobRunner constructs a runner using the default http.Client.
func NewCloudRunJobRunner(project, region, jobName string) *CloudRunJobRunner {
	return &CloudRunJobRunner{
		Project: project,
		Region:  region,
		JobName: jobName,
		Client:  &http.Client{},
	}
}

// runJobURL returns the Cloud Run Jobs API endpoint for running an execution.
func (r *CloudRunJobRunner) runJobURL() string {
	return fmt.Sprintf(
		"https://%s-run.googleapis.com/v2/projects/%s/locations/%s/jobs/%s:run",
		r.Region, r.Project, r.Region, r.JobName,
	)
}

// accessToken fetches a short-lived access token from the GCE metadata server.
// This works inside Cloud Run (and any GCE-based environment).
func (r *CloudRunJobRunner) accessToken(ctx context.Context) (string, error) {
	req, err := http.NewRequestWithContext(
		ctx,
		http.MethodGet,
		"http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/token",
		nil,
	)
	if err != nil {
		return "", fmt.Errorf("build metadata request: %w", err)
	}
	req.Header.Set("Metadata-Flavor", "Google")

	resp, err := r.Client.Do(req)
	if err != nil {
		return "", fmt.Errorf("metadata request: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		return "", fmt.Errorf("metadata server returned %d", resp.StatusCode)
	}

	var tok struct {
		AccessToken string `json:"access_token"`
	}
	if err := json.NewDecoder(resp.Body).Decode(&tok); err != nil {
		return "", fmt.Errorf("decode token response: %w", err)
	}
	if tok.AccessToken == "" {
		return "", fmt.Errorf("empty access token from metadata server")
	}
	return tok.AccessToken, nil
}

// Execute calls the Cloud Run Jobs API to start an execution of the job,
// passing the per-video environment variable overrides.
func (r *CloudRunJobRunner) Execute(ctx context.Context, req ExecuteRequest) error {
	token, err := r.accessToken(ctx)
	if err != nil {
		return fmt.Errorf("get access token: %w", err)
	}

	body := buildRunBody(req)
	bodyBytes, err := json.Marshal(body)
	if err != nil {
		return fmt.Errorf("marshal run body: %w", err)
	}

	httpReq, err := http.NewRequestWithContext(
		ctx,
		http.MethodPost,
		r.runJobURL(),
		strings.NewReader(string(bodyBytes)),
	)
	if err != nil {
		return fmt.Errorf("build run request: %w", err)
	}
	httpReq.Header.Set("Content-Type", "application/json")
	httpReq.Header.Set("Authorization", "Bearer "+token)

	resp, err := r.Client.Do(httpReq)
	if err != nil {
		return fmt.Errorf("run job request: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode < 200 || resp.StatusCode >= 300 {
		raw, _ := io.ReadAll(resp.Body)
		return fmt.Errorf("run job API returned %d: %s", resp.StatusCode, string(raw))
	}
	return nil
}

// runBody is the JSON payload for the Cloud Run Jobs run API.
type runBody struct {
	Overrides runOverrides `json:"overrides"`
}

type runOverrides struct {
	ContainerOverrides []containerOverride `json:"containerOverrides"`
}

type containerOverride struct {
	Env []envVar `json:"env"`
}

type envVar struct {
	Name  string `json:"name"`
	Value string `json:"value"`
}

// buildRunBody constructs the request body that overrides env vars for the job.
func buildRunBody(req ExecuteRequest) runBody {
	return runBody{
		Overrides: runOverrides{
			ContainerOverrides: []containerOverride{
				{
					Env: []envVar{
						{Name: "RAW_OBJECT_PATH", Value: req.RawObjectPath},
						{Name: "VIDEO_ID", Value: req.VideoID},
						{Name: "HLS_BUCKET", Value: req.HLSBucket},
					},
				},
			},
		},
	}
}
