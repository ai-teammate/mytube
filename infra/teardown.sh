#!/usr/bin/env bash
# infra/teardown.sh — Remove all mytube transcoding pipeline resources.
#
# WARNING: This script deletes GCS buckets and their contents, the Cloud Run
# Job, the trigger service, the Eventarc trigger, and the service account.
# It is intended for development / CI tear-down only.
#
# Usage:
#   GCP_PROJECT_ID=my-project GCP_REGION=us-central1 ./infra/teardown.sh

set -euo pipefail

PROJECT="${GCP_PROJECT_ID:?GCP_PROJECT_ID must be set}"
REGION="${GCP_REGION:?GCP_REGION must be set}"

RAW_BUCKET="mytube-raw-uploads"
HLS_BUCKET="mytube-hls-output"
TRANSCODER_SA="mytube-transcoder"
TRANSCODER_SA_EMAIL="${TRANSCODER_SA}@${PROJECT}.iam.gserviceaccount.com"
TRIGGER_SERVICE="mytube-transcoder-trigger"
JOB_NAME="mytube-transcoder"
TRIGGER_NAME="mytube-gcs-finalize"

echo "==> Tearing down mytube transcoding pipeline..."
echo "    Project: ${PROJECT} / Region: ${REGION}"
echo ""

# Eventarc trigger
echo "==> Deleting Eventarc trigger: ${TRIGGER_NAME}..."
gcloud eventarc triggers delete "${TRIGGER_NAME}" \
  --location="${REGION}" \
  --project="${PROJECT}" \
  --quiet || echo "    Not found, skipping."

# Cloud Run trigger service
echo ""
echo "==> Deleting Cloud Run service: ${TRIGGER_SERVICE}..."
gcloud run services delete "${TRIGGER_SERVICE}" \
  --region="${REGION}" \
  --project="${PROJECT}" \
  --quiet || echo "    Not found, skipping."

# Cloud Run Job
echo ""
echo "==> Deleting Cloud Run Job: ${JOB_NAME}..."
gcloud run jobs delete "${JOB_NAME}" \
  --region="${REGION}" \
  --project="${PROJECT}" \
  --quiet || echo "    Not found, skipping."

# GCS buckets (force-delete including contents)
echo ""
echo "==> Deleting GCS bucket: ${RAW_BUCKET}..."
gcloud storage rm -r "gs://${RAW_BUCKET}" \
  --project="${PROJECT}" || echo "    Not found, skipping."

echo ""
echo "==> Deleting GCS bucket: ${HLS_BUCKET}..."
gcloud storage rm -r "gs://${HLS_BUCKET}" \
  --project="${PROJECT}" || echo "    Not found, skipping."

# Service account
echo ""
echo "==> Deleting service account: ${TRANSCODER_SA_EMAIL}..."
gcloud iam service-accounts delete "${TRANSCODER_SA_EMAIL}" \
  --project="${PROJECT}" \
  --quiet || echo "    Not found, skipping."

echo ""
echo "==> Teardown complete."
