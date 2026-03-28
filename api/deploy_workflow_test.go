package main_test

import (
	"os"
	"strings"
	"testing"
)

// TestDeployWorkflowRevisionCleanupToleratesErrors validates that the
// "Delete old Cloud Run revisions" step in deploy-api.yml uses error-tolerant
// deletion commands (i.e., the xargs block includes "|| true" so that a failing
// gcloud call does not abort the CI pipeline).
//
// Root cause (MYTUBE-73): commit acce608 changed `tail -n +3` to `tail -n +2`
// in both the revision and GCR image cleanup steps. This meant the workflow
// tried to delete more aggressively. When gcloud run revisions delete returns a
// non-zero exit for any revision (e.g., still-draining traffic), xargs
// propagates that exit code and the entire CI step fails. Adding "|| true"
// makes the cleanup best-effort without affecting the deployment itself.
func TestDeployWorkflowRevisionCleanupToleratesErrors(t *testing.T) {
	workflowPath := "../.github/workflows/deploy-api.yml"
	data, err := os.ReadFile(workflowPath)
	if err != nil {
		t.Fatalf("cannot read deploy-api.yml: %v", err)
	}
	content := string(data)

	if !strings.Contains(content, "revisions delete") {
		t.Skip("no revision delete step found in workflow — skipping")
	}

	// Extract the block between "xargs" (containing "revisions delete") and the
	// closing "fi" of that if-block. The "|| true" may appear on any continuation
	// line (e.g. on the "--quiet || true" line), so we check the entire block.
	lines := strings.Split(content, "\n")
	inBlock := false
	blockLines := []string{}

	for _, line := range lines {
		// Match both old xargs pattern and new loop pattern
		if strings.Contains(line, "revisions delete") {
			inBlock = true
		}
		if inBlock {
			blockLines = append(blockLines, line)
			trimmed := strings.TrimSpace(line)
			// The block ends at the closing "fi" or "done"
			if trimmed == "fi" || trimmed == "done" {
				break
			}
		}
	}

	if len(blockLines) == 0 {
		t.Fatal("could not find revision deletion block in workflow")
	}

	block := strings.Join(blockLines, "\n")
	if !strings.Contains(block, "|| true") {
		t.Errorf("revision deletion block does not contain '|| true' to tolerate errors.\n"+
			"Block:\n%s", block)
	}
}

// TestDeployWorkflowImageCleanupToleratesErrors validates that the
// "Delete old GCR images" step in deploy-api.yml uses error-tolerant deletion.
func TestDeployWorkflowImageCleanupToleratesErrors(t *testing.T) {
	workflowPath := "../.github/workflows/deploy-api.yml"
	data, err := os.ReadFile(workflowPath)
	if err != nil {
		t.Fatalf("cannot read deploy-api.yml: %v", err)
	}
	content := string(data)

	if !strings.Contains(content, "images delete") {
		t.Skip("no image delete step found in workflow — skipping")
	}

	lines := strings.Split(content, "\n")
	inBlock := false
	blockLines := []string{}

	for _, line := range lines {
		// Match both old xargs pattern and new loop pattern
		if strings.Contains(line, "images delete") {
			inBlock = true
		}
		if inBlock {
			blockLines = append(blockLines, line)
			trimmed := strings.TrimSpace(line)
			if trimmed == "fi" || trimmed == "done" {
				break
			}
		}
	}

	if len(blockLines) == 0 {
		t.Fatal("could not find image deletion block in workflow")
	}

	block := strings.Join(blockLines, "\n")
	// Accept either explicit "|| true" or structured error handling (FAILED counter)
	if !strings.Contains(block, "|| true") && !strings.Contains(block, "FAILED=") {
		t.Errorf("image deletion block does not contain error-tolerant handling ('|| true' or FAILED counter).\n"+
			"Block:\n%s", block)
	}
}
