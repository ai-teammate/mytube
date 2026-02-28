// Package handler provides the HTTP handler for the Eventarc trigger service.
package handler

import (
	"context"
	"log"
	"net/http"

	"github.com/ai-teammate/mytube/infra/transcoder-trigger/internal/event"
	"github.com/ai-teammate/mytube/infra/transcoder-trigger/internal/jobs"
)

// JobExecutor is the interface the handler depends on to start a Cloud Run Job.
// It is satisfied by *jobs.CloudRunJobRunner and allows tests to inject a mock.
type JobExecutor interface {
	Execute(ctx context.Context, req jobs.ExecuteRequest) error
}

// NewTriggerHandler returns an http.HandlerFunc that:
//  1. Parses the GCS StorageObject from the Eventarc request body.
//  2. Extracts the VIDEO_ID from the object name.
//  3. Calls executor.Execute with the job env-var overrides.
//
// hlsBucket is the destination GCS bucket passed to the transcoder job.
func NewTriggerHandler(executor JobExecutor, hlsBucket string) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		obj, err := event.Parse(r.Body)
		if err != nil {
			log.Printf("trigger: parse event: %v", err)
			http.Error(w, "bad request", http.StatusBadRequest)
			return
		}

		videoID, err := obj.VideoID()
		if err != nil {
			log.Printf("trigger: extract video ID: %v", err)
			http.Error(w, "bad request", http.StatusBadRequest)
			return
		}

		req := jobs.ExecuteRequest{
			RawObjectPath: obj.Name,
			VideoID:       videoID,
			HLSBucket:     hlsBucket,
		}

		if err := executor.Execute(r.Context(), req); err != nil {
			log.Printf("trigger: execute job: %v", err)
			http.Error(w, "internal error", http.StatusInternalServerError)
			return
		}

		w.WriteHeader(http.StatusNoContent)
	}
}
