package main

import (
	"log"
	"net/http"
	"os"

	"github.com/ai-teammate/mytube/infra/transcoder-trigger/internal/handler"
	"github.com/ai-teammate/mytube/infra/transcoder-trigger/internal/jobs"
)

func main() {
	project := mustEnv("GCP_PROJECT")
	region := mustEnv("GCP_REGION")
	jobName := mustEnv("JOB_NAME")
	hlsBucket := mustEnv("HLS_BUCKET")

	runner := jobs.NewCloudRunJobRunner(project, region, jobName)

	mux := http.NewServeMux()
	mux.HandleFunc("/", handler.NewTriggerHandler(runner, hlsBucket))

	port := os.Getenv("PORT")
	if port == "" {
		port = "8080"
	}

	log.Printf("transcoder-trigger listening on :%s (job=%s project=%s region=%s)",
		port, jobName, project, region)
	log.Fatal(http.ListenAndServe(":"+port, mux))
}

// mustEnv returns the value of the environment variable or fatals.
func mustEnv(key string) string {
	v := os.Getenv(key)
	if v == "" {
		log.Fatalf("required environment variable %s is not set", key)
	}
	return v
}
