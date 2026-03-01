#!/usr/bin/env bash
# infra/setup.sh — Provision GCS buckets, IAM, Cloud Run Job, and Eventarc trigger
# for the mytube transcoding pipeline.
#
# Prerequisites:
#   - gcloud CLI authenticated with a principal that has sufficient permissions
#   - GCP_PROJECT_ID, GCP_REGION environment variables set (or edit defaults below)
#
# Usage:
#   GCP_PROJECT_ID=my-project GCP_REGION=us-central1 ./infra/setup.sh

set -euo pipefail

# ── Configuration ──────────────────────────────────────────────────────────────
PROJECT="${GCP_PROJECT_ID:?GCP_PROJECT_ID must be set}"
REGION="${GCP_REGION:?GCP_REGION must be set}"

RAW_BUCKET="mytube-raw-uploads"
HLS_BUCKET="mytube-hls-output"
TRANSCODER_SA="mytube-transcoder"
TRANSCODER_SA_EMAIL="${TRANSCODER_SA}@${PROJECT}.iam.gserviceaccount.com"
TRIGGER_SERVICE="mytube-transcoder-trigger"
JOB_NAME="mytube-transcoder"

echo "==> Project : ${PROJECT}"
echo "==> Region  : ${REGION}"
echo ""

# ── 1. Enable required APIs ────────────────────────────────────────────────────
echo "==> Enabling required APIs..."
gcloud services enable \
  storage.googleapis.com \
  run.googleapis.com \
  eventarc.googleapis.com \
  pubsub.googleapis.com \
  --project="${PROJECT}"

# ── 2. Create GCS buckets ─────────────────────────────────────────────────────
echo ""
echo "==> Creating GCS bucket: ${RAW_BUCKET} (private)..."
if ! gcloud storage buckets describe "gs://${RAW_BUCKET}" --project="${PROJECT}" &>/dev/null; then
  gcloud storage buckets create "gs://${RAW_BUCKET}" \
    --location="${REGION}" \
    --uniform-bucket-level-access \
    --no-public-access-prevention \
    --project="${PROJECT}"
  echo "    Created gs://${RAW_BUCKET}"
else
  echo "    gs://${RAW_BUCKET} already exists, skipping."
fi

echo ""
echo "==> Creating GCS bucket: ${HLS_BUCKET} (public read)..."
if ! gcloud storage buckets describe "gs://${HLS_BUCKET}" --project="${PROJECT}" &>/dev/null; then
  gcloud storage buckets create "gs://${HLS_BUCKET}" \
    --location="${REGION}" \
    --uniform-bucket-level-access \
    --no-public-access-prevention \
    --project="${PROJECT}"

  # Grant public read access for HLS delivery.
  gcloud storage buckets add-iam-policy-binding "gs://${HLS_BUCKET}" \
    --member="allUsers" \
    --role="roles/storage.objectViewer" \
    --project="${PROJECT}"

  echo "    Created gs://${HLS_BUCKET} with allUsers objectViewer"
else
  echo "    gs://${HLS_BUCKET} already exists, skipping."
fi

# ── 3. Create dedicated transcoder service account ────────────────────────────
echo ""
echo "==> Creating service account: ${TRANSCODER_SA_EMAIL}..."
if ! gcloud iam service-accounts describe "${TRANSCODER_SA_EMAIL}" \
    --project="${PROJECT}" &>/dev/null; then
  gcloud iam service-accounts create "${TRANSCODER_SA}" \
    --display-name="mytube Transcoder" \
    --description="Least-privilege SA for the mytube-transcoder Cloud Run Job" \
    --project="${PROJECT}"
  echo "    Created ${TRANSCODER_SA_EMAIL}"
else
  echo "    ${TRANSCODER_SA_EMAIL} already exists, skipping."
fi

# ── 4. Grant IAM on buckets ───────────────────────────────────────────────────
echo ""
echo "==> Granting ${TRANSCODER_SA_EMAIL} objectViewer on ${RAW_BUCKET}..."
gcloud storage buckets add-iam-policy-binding "gs://${RAW_BUCKET}" \
  --member="serviceAccount:${TRANSCODER_SA_EMAIL}" \
  --role="roles/storage.objectViewer" \
  --project="${PROJECT}"

echo ""
echo "==> Granting ${TRANSCODER_SA_EMAIL} objectCreator on ${HLS_BUCKET}..."
gcloud storage buckets add-iam-policy-binding "gs://${HLS_BUCKET}" \
  --member="serviceAccount:${TRANSCODER_SA_EMAIL}" \
  --role="roles/storage.objectCreator" \
  --project="${PROJECT}"

# ── 5. Allow trigger service to invoke Cloud Run Jobs ─────────────────────────
# The trigger Cloud Run Service needs run.jobs.run permission.
echo ""
echo "==> Granting ${TRANSCODER_SA_EMAIL} run.developer on project (to execute Jobs)..."
gcloud projects add-iam-policy-binding "${PROJECT}" \
  --member="serviceAccount:${TRANSCODER_SA_EMAIL}" \
  --role="roles/run.developer"

# ── 6. Create the Cloud Run Job (transcoder placeholder) ─────────────────────
# The actual FFmpeg logic is in a separate story; the Job is created with a
# placeholder image so the Eventarc trigger can reference a real job name.
echo ""
echo "==> Creating Cloud Run Job: ${JOB_NAME}..."
if ! gcloud run jobs describe "${JOB_NAME}" \
    --region="${REGION}" \
    --project="${PROJECT}" &>/dev/null; then
  gcloud run jobs create "${JOB_NAME}" \
    --image="gcr.io/google-containers/pause:3.5" \
    --region="${REGION}" \
    --service-account="${TRANSCODER_SA_EMAIL}" \
    --set-env-vars="HLS_BUCKET=${HLS_BUCKET}" \
    --max-retries=1 \
    --task-timeout=3600 \
    --project="${PROJECT}"
  echo "    Created Cloud Run Job ${JOB_NAME}"
else
  echo "    Cloud Run Job ${JOB_NAME} already exists, skipping."
fi

# ── 7. Deploy the Eventarc trigger Cloud Run Service ─────────────────────────
# mytube-transcoder-trigger: a lightweight Go service that receives the GCS
# finalize event and calls the Cloud Run Jobs API to start mytube-transcoder.
echo ""
echo "==> Deploying trigger service: ${TRIGGER_SERVICE}..."
echo "    (Build and push the image first; see infra/transcoder-trigger/)"
echo "    To deploy after building the image, run:"
echo ""
echo "    IMAGE=gcr.io/${PROJECT}/${TRIGGER_SERVICE}:latest"
echo "    docker build -t \$IMAGE ./infra/transcoder-trigger"
echo "    docker push \$IMAGE"
echo "    gcloud run deploy ${TRIGGER_SERVICE} \\"
echo "      --image \$IMAGE \\"
echo "      --region ${REGION} \\"
echo "      --platform managed \\"
echo "      --no-allow-unauthenticated \\"
echo "      --service-account ${TRANSCODER_SA_EMAIL} \\"
echo "      --set-env-vars JOB_NAME=${JOB_NAME},GCP_REGION=${REGION},GCP_PROJECT=${PROJECT} \\"
echo "      --project ${PROJECT}"
echo ""

# ── 8. Create Eventarc trigger ────────────────────────────────────────────────
# Note: run the trigger-service deploy first; this step references its URL.
echo "==> To create the Eventarc trigger (after deploying ${TRIGGER_SERVICE}), run:"
echo ""
echo "    TRIGGER_URL=\$(gcloud run services describe ${TRIGGER_SERVICE} \\"
echo "      --region ${REGION} --project ${PROJECT} --format 'value(status.url)')"
echo ""
echo "    # Grant the GCS service account permission to invoke the trigger service."
echo "    GCS_SA=\$(gcloud storage service-agent --project ${PROJECT})"
echo "    gcloud run services add-iam-policy-binding ${TRIGGER_SERVICE} \\"
echo "      --region ${REGION} \\"
echo "      --project ${PROJECT} \\"
echo "      --member \"serviceAccount:\${GCS_SA}\" \\"
echo "      --role roles/run.invoker"
echo ""
echo "    gcloud eventarc triggers create mytube-gcs-finalize \\"
echo "      --location=${REGION} \\"
echo "      --destination-run-service=${TRIGGER_SERVICE} \\"
echo "      --destination-run-region=${REGION} \\"
echo "      --event-filters=type=google.cloud.storage.object.v1.finalized \\"
echo "      --event-filters=bucket=${RAW_BUCKET} \\"
echo "      --service-account=${TRANSCODER_SA_EMAIL} \\"
echo "      --project=${PROJECT}"
echo ""
echo "==> Setup complete."
