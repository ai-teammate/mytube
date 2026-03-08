package main_test

import (
	"os"
	"strings"
	"testing"
)

// TestProvisionWorkflowTranscoderSADeleteOnRawUploads verifies that the
// provision-gcs-buckets.yml workflow grants the transcoder SA a role that
// includes storage.objects.delete on the raw-uploads bucket.
//
// Root cause (MYTUBE-387): the workflow previously used roles/storage.objectViewer
// (read-only) for the transcoder SA on raw-uploads. After transcoding, the raw
// source object must be deletable to prevent storage leakage.
func TestProvisionWorkflowTranscoderSADeleteOnRawUploads(t *testing.T) {
	content := readWorkflow(t, "../.github/workflows/provision-gcs-buckets.yml")

	// The role granted to the transcoder SA on raw-uploads must NOT be objectViewer
	// (read-only) or objectCreator (write-only). It must be objectUser or objectAdmin.
	if strings.Contains(content, "objectViewer") {
		// objectViewer may appear in the CI SA section — only fail if it appears near
		// the transcoder SA + RAW_BUCKET block.
		lines := strings.Split(content, "\n")
		inTranscoderRawBlock := false
		for _, line := range lines {
			if strings.Contains(line, "TRANSCODER_SA") && strings.Contains(line, "RAW_BUCKET") {
				inTranscoderRawBlock = true
			}
			if inTranscoderRawBlock && strings.Contains(line, "objectViewer") {
				t.Errorf("provision-gcs-buckets.yml grants objectViewer to transcoder SA on "+
					"raw-uploads bucket. objectViewer does not include storage.objects.delete. "+
					"Use roles/storage.objectUser instead.\nLine: %s", strings.TrimSpace(line))
				break
			}
		}
	}

	// Must find a block that grants a delete-capable role to the transcoder SA on raw-uploads.
	if !workflowContainsTranscoderDeleteOnRaw(content) {
		t.Errorf("provision-gcs-buckets.yml does not grant transcoder SA a delete-capable " +
			"role (objectUser or objectAdmin) on the raw-uploads bucket. " +
			"Any code path that deletes the raw source after transcoding will fail with AccessDenied.")
	}
}

// TestProvisionWorkflowTranscoderSADeleteOnHlsOutput verifies that the
// provision-gcs-buckets.yml workflow grants the transcoder SA a delete-capable
// role on the hls-output bucket.
//
// Root cause (MYTUBE-387): the workflow granted roles/storage.objectCreator
// (write, no delete). Re-transcoding or HLS cleanup requires delete permission.
func TestProvisionWorkflowTranscoderSADeleteOnHlsOutput(t *testing.T) {
	content := readWorkflow(t, "../.github/workflows/provision-gcs-buckets.yml")

	if !workflowContainsTranscoderDeleteOnHls(content) {
		t.Errorf("provision-gcs-buckets.yml does not grant transcoder SA a delete-capable " +
			"role (objectAdmin or objectUser) on the hls-output bucket. " +
			"Re-transcoding and HLS cleanup will fail with AccessDenied.")
	}
}

// TestProvisionWorkflowAPISADeleteOnRawUploads verifies that the
// provision-gcs-buckets.yml workflow grants the API server SA a delete-capable
// role on the raw-uploads bucket.
//
// Root cause (MYTUBE-387): no IAM binding existed for the API SA on raw-uploads.
// The API server must delete raw-upload objects (e.g., on video delete or failed upload).
func TestProvisionWorkflowAPISADeleteOnRawUploads(t *testing.T) {
	content := readWorkflow(t, "../.github/workflows/provision-gcs-buckets.yml")

	// Look for a step that grants the API SA (or API_SA env var) objectUser/objectAdmin
	// on the raw-uploads bucket.
	if !workflowContainsAPISADeleteOnRaw(content) {
		t.Errorf("provision-gcs-buckets.yml does not grant the API server SA a delete-capable " +
			"role (objectUser or objectAdmin) on the raw-uploads bucket. " +
			"API-driven cleanup will fail with AccessDenied.")
	}
}

// TestProvisionWorkflowAPISADeleteOnHlsOutput verifies that the
// provision-gcs-buckets.yml workflow grants the API server SA a delete-capable
// role on the hls-output bucket.
//
// Root cause (MYTUBE-387): no IAM binding existed for the API SA on hls-output.
// The API server must delete HLS segments when a video is removed.
func TestProvisionWorkflowAPISADeleteOnHlsOutput(t *testing.T) {
	content := readWorkflow(t, "../.github/workflows/provision-gcs-buckets.yml")

	if !workflowContainsAPISADeleteOnHls(content) {
		t.Errorf("provision-gcs-buckets.yml does not grant the API server SA a delete-capable " +
			"role (objectUser or objectAdmin) on the hls-output bucket. " +
			"Video-delete HLS cleanup will fail with AccessDenied.")
	}
}

// TestSetupShTranscoderSADeleteOnRawUploads verifies that infra/setup.sh grants
// the transcoder SA a delete-capable role on the raw-uploads bucket.
func TestSetupShTranscoderSADeleteOnRawUploads(t *testing.T) {
	data, err := os.ReadFile("../infra/setup.sh")
	if err != nil {
		t.Fatalf("cannot read infra/setup.sh: %v", err)
	}
	content := string(data)

	// setup.sh must not grant objectViewer to the transcoder SA on raw-uploads.
	lines := strings.Split(content, "\n")
	for i, line := range lines {
		if strings.Contains(line, "TRANSCODER_SA_EMAIL") &&
			strings.Contains(line, "RAW_BUCKET") &&
			strings.Contains(line, "objectViewer") {
			t.Errorf("infra/setup.sh line %d grants objectViewer to transcoder SA on "+
				"raw-uploads bucket (no delete permission). Use objectUser instead.\nLine: %s",
				i+1, strings.TrimSpace(line))
		}
	}

	// Must have objectUser or objectAdmin for transcoder SA on raw-uploads.
	if !setupShContainsTranscoderObjectUserOnRaw(content) {
		t.Errorf("infra/setup.sh does not grant transcoder SA objectUser or objectAdmin " +
			"on the raw-uploads bucket.")
	}
}

// TestSetupShAPISADeleteOnBothBuckets verifies that infra/setup.sh grants the
// API server SA delete-capable roles on both GCS buckets.
func TestSetupShAPISADeleteOnBothBuckets(t *testing.T) {
	data, err := os.ReadFile("../infra/setup.sh")
	if err != nil {
		t.Fatalf("cannot read infra/setup.sh: %v", err)
	}
	content := string(data)

	if !strings.Contains(content, "API_SA") && !strings.Contains(content, "api_sa") &&
		!strings.Contains(content, "API_SERVER_SA") {
		t.Errorf("infra/setup.sh does not contain any API SA variable or grant. " +
			"The API server SA needs objectUser or objectAdmin on both GCS buckets.")
	}
}

// ── helpers ───────────────────────────────────────────────────────────────────

func readWorkflow(t *testing.T, path string) string {
	t.Helper()
	data, err := os.ReadFile(path)
	if err != nil {
		t.Fatalf("cannot read %s: %v", path, err)
	}
	return string(data)
}

// workflowContainsTranscoderDeleteOnRaw checks for a delete-capable role grant
// to the transcoder SA on the raw-uploads bucket.
func workflowContainsTranscoderDeleteOnRaw(content string) bool {
	deleteRoles := []string{"objectUser", "objectAdmin", "storage.admin", "legacyObjectOwner"}
	lines := strings.Split(content, "\n")
	for i, line := range lines {
		// Look for the block referencing TRANSCODER_SA and RAW_BUCKET
		if strings.Contains(line, "TRANSCODER_SA") {
			// Scan surrounding lines for a delete-capable role
			start := max(0, i-5)
			end := min(len(lines), i+15)
			block := strings.Join(lines[start:end], "\n")
			if strings.Contains(block, "RAW_BUCKET") || strings.Contains(block, "raw-uploads") {
				for _, role := range deleteRoles {
					if strings.Contains(block, role) {
						return true
					}
				}
			}
		}
	}
	return false
}

// workflowContainsTranscoderDeleteOnHls checks for a delete-capable role grant
// to the transcoder SA on the hls-output bucket.
func workflowContainsTranscoderDeleteOnHls(content string) bool {
	deleteRoles := []string{"objectAdmin", "objectUser", "storage.admin", "legacyObjectOwner"}
	lines := strings.Split(content, "\n")
	for i, line := range lines {
		if strings.Contains(line, "TRANSCODER_SA") {
			start := max(0, i-5)
			end := min(len(lines), i+15)
			block := strings.Join(lines[start:end], "\n")
			if strings.Contains(block, "HLS_BUCKET") || strings.Contains(block, "hls-output") {
				for _, role := range deleteRoles {
					if strings.Contains(block, role) {
						return true
					}
				}
			}
		}
	}
	return false
}

// workflowContainsAPISADeleteOnRaw checks that the workflow grants a delete-capable
// role to an API SA variable on the raw-uploads bucket.
func workflowContainsAPISADeleteOnRaw(content string) bool {
	return containsAPISAGrantOnBucket(content, "RAW_BUCKET", "raw-uploads")
}

// workflowContainsAPISADeleteOnHls checks that the workflow grants a delete-capable
// role to an API SA variable on the hls-output bucket.
func workflowContainsAPISADeleteOnHls(content string) bool {
	return containsAPISAGrantOnBucket(content, "HLS_BUCKET", "hls-output")
}

// containsAPISAGrantOnBucket scans for an add-iam-policy-binding block that
// references an API SA variable and the specified bucket, with a delete-capable role.
func containsAPISAGrantOnBucket(content, bucketVar, bucketName string) bool {
	apiSAKeywords := []string{"API_SA", "api_sa", "API_SERVER_SA", "api_server_sa"}
	deleteRoles := []string{"objectUser", "objectAdmin", "storage.admin", "legacyObjectOwner"}
	lines := strings.Split(content, "\n")
	for i, line := range lines {
		for _, kw := range apiSAKeywords {
			if strings.Contains(line, kw) {
				start := max(0, i-5)
				end := min(len(lines), i+15)
				block := strings.Join(lines[start:end], "\n")
				if strings.Contains(block, bucketVar) || strings.Contains(block, bucketName) {
					for _, role := range deleteRoles {
						if strings.Contains(block, role) {
							return true
						}
					}
				}
			}
		}
	}
	return false
}

// setupShContainsTranscoderObjectUserOnRaw checks that setup.sh grants
// objectUser or objectAdmin to the transcoder SA on the raw-uploads bucket.
func setupShContainsTranscoderObjectUserOnRaw(content string) bool {
	deleteRoles := []string{"objectUser", "objectAdmin", "storage.admin", "legacyObjectOwner"}
	lines := strings.Split(content, "\n")
	for i, line := range lines {
		if strings.Contains(line, "TRANSCODER_SA_EMAIL") {
			start := max(0, i-2)
			end := min(len(lines), i+10)
			block := strings.Join(lines[start:end], "\n")
			if strings.Contains(block, "RAW_BUCKET") || strings.Contains(block, "raw-uploads") {
				for _, role := range deleteRoles {
					if strings.Contains(block, role) {
						return true
					}
				}
			}
		}
	}
	return false
}

func max(a, b int) int {
	if a > b {
		return a
	}
	return b
}

func min(a, b int) int {
	if a < b {
		return a
	}
	return b
}
