package jobs_test

import (
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"strings"
	"testing"

	"github.com/ai-teammate/mytube/infra/transcoder-trigger/internal/jobs"
)

// ── stubHTTPDoer ──────────────────────────────────────────────────────────────

// stubDoer implements jobs.HTTPDoer and records calls.
type stubDoer struct {
	responses []*http.Response
	errors    []error
	calls     []*http.Request
	index     int
}

func (s *stubDoer) Do(req *http.Request) (*http.Response, error) {
	s.calls = append(s.calls, req)
	if s.index >= len(s.responses) {
		return nil, fmt.Errorf("stubDoer: unexpected call %d", s.index)
	}
	resp := s.responses[s.index]
	var err error
	if s.index < len(s.errors) {
		err = s.errors[s.index]
	}
	s.index++
	return resp, err
}

// okMetadataResponse returns a fake metadata server response with a token.
func okMetadataResponse(token string) *http.Response {
	body := fmt.Sprintf(`{"access_token":%q,"expires_in":3599,"token_type":"Bearer"}`, token)
	return &http.Response{
		StatusCode: http.StatusOK,
		Body:       io.NopCloser(strings.NewReader(body)),
	}
}

// okRunResponse returns a fake successful Cloud Run Jobs API response.
func okRunResponse() *http.Response {
	return &http.Response{
		StatusCode: http.StatusOK,
		Body:       io.NopCloser(strings.NewReader(`{"name":"projects/p/locations/r/jobs/j/executions/e"}`)),
	}
}

// ── NewCloudRunJobRunner ──────────────────────────────────────────────────────

func TestNewCloudRunJobRunner_Fields(t *testing.T) {
	r := jobs.NewCloudRunJobRunner("my-project", "us-central1", "my-job")
	if r.Project != "my-project" {
		t.Errorf("expected project my-project, got %q", r.Project)
	}
	if r.Region != "us-central1" {
		t.Errorf("expected region us-central1, got %q", r.Region)
	}
	if r.JobName != "my-job" {
		t.Errorf("expected job my-job, got %q", r.JobName)
	}
	if r.Client == nil {
		t.Error("expected non-nil Client")
	}
}

// ── Execute success ───────────────────────────────────────────────────────────

func TestExecute_Success(t *testing.T) {
	doer := &stubDoer{
		responses: []*http.Response{
			okMetadataResponse("tok123"),
			okRunResponse(),
		},
	}

	runner := &jobs.CloudRunJobRunner{
		Project: "proj",
		Region:  "us-central1",
		JobName: "mytube-transcoder",
		Client:  doer,
	}

	err := runner.Execute(context.Background(), jobs.ExecuteRequest{
		RawObjectPath: "raw/abc.mp4",
		VideoID:       "abc",
		HLSBucket:     "mytube-hls-output",
	})
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if doer.index != 2 {
		t.Errorf("expected 2 HTTP calls, got %d", doer.index)
	}
}

func TestExecute_BearerTokenInRunRequest(t *testing.T) {
	doer := &stubDoer{
		responses: []*http.Response{
			okMetadataResponse("my-access-token"),
			okRunResponse(),
		},
	}
	runner := &jobs.CloudRunJobRunner{
		Project: "proj",
		Region:  "us-central1",
		JobName: "mytube-transcoder",
		Client:  doer,
	}
	_ = runner.Execute(context.Background(), jobs.ExecuteRequest{
		RawObjectPath: "raw/uuid.mp4",
		VideoID:       "uuid",
		HLSBucket:     "hls-bucket",
	})

	// Second call is the run-job request.
	runReq := doer.calls[1]
	auth := runReq.Header.Get("Authorization")
	if auth != "Bearer my-access-token" {
		t.Errorf("expected Authorization header 'Bearer my-access-token', got %q", auth)
	}
}

func TestExecute_RunRequestBodyContainsEnvVars(t *testing.T) {
	doer := &stubDoer{
		responses: []*http.Response{
			okMetadataResponse("tok"),
			okRunResponse(),
		},
	}
	runner := &jobs.CloudRunJobRunner{
		Project: "proj",
		Region:  "us-central1",
		JobName: "mytube-transcoder",
		Client:  doer,
	}
	_ = runner.Execute(context.Background(), jobs.ExecuteRequest{
		RawObjectPath: "raw/vid.mp4",
		VideoID:       "vid",
		HLSBucket:     "my-hls",
	})

	runReq := doer.calls[1]
	rawBody, _ := io.ReadAll(runReq.Body)

	// Validate JSON structure has the env var overrides.
	var payload map[string]interface{}
	if err := json.Unmarshal(rawBody, &payload); err != nil {
		t.Fatalf("invalid JSON body: %v", err)
	}
	overrides, ok := payload["overrides"].(map[string]interface{})
	if !ok {
		t.Fatal("missing overrides field")
	}
	containers, ok := overrides["containerOverrides"].([]interface{})
	if !ok || len(containers) == 0 {
		t.Fatal("missing containerOverrides")
	}
	container := containers[0].(map[string]interface{})
	envList := container["env"].([]interface{})

	envMap := make(map[string]string)
	for _, e := range envList {
		entry := e.(map[string]interface{})
		envMap[entry["name"].(string)] = entry["value"].(string)
	}

	if envMap["RAW_OBJECT_PATH"] != "raw/vid.mp4" {
		t.Errorf("unexpected RAW_OBJECT_PATH: %q", envMap["RAW_OBJECT_PATH"])
	}
	if envMap["VIDEO_ID"] != "vid" {
		t.Errorf("unexpected VIDEO_ID: %q", envMap["VIDEO_ID"])
	}
	if envMap["HLS_BUCKET"] != "my-hls" {
		t.Errorf("unexpected HLS_BUCKET: %q", envMap["HLS_BUCKET"])
	}
}

func TestExecute_RunRequestURLContainsJobName(t *testing.T) {
	doer := &stubDoer{
		responses: []*http.Response{
			okMetadataResponse("tok"),
			okRunResponse(),
		},
	}
	runner := &jobs.CloudRunJobRunner{
		Project: "my-project",
		Region:  "us-east1",
		JobName: "special-job",
		Client:  doer,
	}
	_ = runner.Execute(context.Background(), jobs.ExecuteRequest{})

	runReq := doer.calls[1]
	url := runReq.URL.String()
	if !strings.Contains(url, "special-job") {
		t.Errorf("expected URL to contain job name 'special-job', got %q", url)
	}
	if !strings.Contains(url, "my-project") {
		t.Errorf("expected URL to contain project 'my-project', got %q", url)
	}
}

// ── Execute metadata errors ───────────────────────────────────────────────────

func TestExecute_MetadataRequestError(t *testing.T) {
	doer := &stubDoer{
		responses: []*http.Response{nil},
		errors:    []error{fmt.Errorf("network error")},
	}
	runner := &jobs.CloudRunJobRunner{
		Project: "p",
		Region:  "r",
		JobName: "j",
		Client:  doer,
	}
	err := runner.Execute(context.Background(), jobs.ExecuteRequest{})
	if err == nil {
		t.Fatal("expected error, got nil")
	}
}

func TestExecute_MetadataServerNonOK(t *testing.T) {
	doer := &stubDoer{
		responses: []*http.Response{
			{
				StatusCode: http.StatusInternalServerError,
				Body:       io.NopCloser(strings.NewReader("error")),
			},
		},
	}
	runner := &jobs.CloudRunJobRunner{
		Project: "p",
		Region:  "r",
		JobName: "j",
		Client:  doer,
	}
	err := runner.Execute(context.Background(), jobs.ExecuteRequest{})
	if err == nil {
		t.Fatal("expected error for non-200 metadata response")
	}
}

func TestExecute_MetadataEmptyToken(t *testing.T) {
	doer := &stubDoer{
		responses: []*http.Response{
			{
				StatusCode: http.StatusOK,
				Body:       io.NopCloser(strings.NewReader(`{"access_token":""}`)),
			},
		},
	}
	runner := &jobs.CloudRunJobRunner{
		Project: "p",
		Region:  "r",
		JobName: "j",
		Client:  doer,
	}
	err := runner.Execute(context.Background(), jobs.ExecuteRequest{})
	if err == nil {
		t.Fatal("expected error for empty access token")
	}
}

func TestExecute_MetadataInvalidJSON(t *testing.T) {
	doer := &stubDoer{
		responses: []*http.Response{
			{
				StatusCode: http.StatusOK,
				Body:       io.NopCloser(strings.NewReader("not-json")),
			},
		},
	}
	runner := &jobs.CloudRunJobRunner{
		Project: "p",
		Region:  "r",
		JobName: "j",
		Client:  doer,
	}
	err := runner.Execute(context.Background(), jobs.ExecuteRequest{})
	if err == nil {
		t.Fatal("expected error for invalid JSON token response")
	}
}

// ── Execute run API errors ────────────────────────────────────────────────────

func TestExecute_RunAPIError(t *testing.T) {
	doer := &stubDoer{
		responses: []*http.Response{
			okMetadataResponse("tok"),
			nil,
		},
		errors: []error{nil, fmt.Errorf("connection refused")},
	}
	runner := &jobs.CloudRunJobRunner{
		Project: "p",
		Region:  "r",
		JobName: "j",
		Client:  doer,
	}
	err := runner.Execute(context.Background(), jobs.ExecuteRequest{})
	if err == nil {
		t.Fatal("expected error, got nil")
	}
}

func TestExecute_RunAPINonOK(t *testing.T) {
	doer := &stubDoer{
		responses: []*http.Response{
			okMetadataResponse("tok"),
			{
				StatusCode: http.StatusForbidden,
				Body:       io.NopCloser(strings.NewReader("permission denied")),
			},
		},
	}
	runner := &jobs.CloudRunJobRunner{
		Project: "p",
		Region:  "r",
		JobName: "j",
		Client:  doer,
	}
	err := runner.Execute(context.Background(), jobs.ExecuteRequest{})
	if err == nil {
		t.Fatal("expected error for non-2xx run API response")
	}
}
