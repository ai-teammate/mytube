# mytube — Stack & Architecture

## Overview
Open-source personal video platform (YouTube-like), built for scale on Google Cloud serverless infrastructure.

## Deployment Constraints

> **All deployments are strictly limited to:**
> - **API** → Google Cloud Run only
> - **Frontend** → GitHub Pages only
>
> No other deployment targets are permitted.

## Stack

| Layer | Technology | Notes |
|-------|-----------|-------|
| API | Go + `net/http` | Cloud Run, scales to 0, ~15MB image |
| Database | PostgreSQL | Cloud SQL |
| Video storage | Google Cloud Storage | Raw uploads + HLS segments |
| Video streaming | GCS + Cloud CDN | Adaptive HLS streaming |
| Transcoding | Cloud Run Jobs + FFmpeg | Triggered on GCS upload (future) |
| Frontend | Next.js (static export) | GitHub Pages via `deploy-pages.yml` |
| Auth | Firebase Auth | Google Sign-in, emulator for testing |

## Live URLs

| Service | URL |
|---------|-----|
| API | https://mytube-api-80693608388.us-central1.run.app |

## Project Structure

```
api/
├── main.go       — HTTP server + DB connection
├── go.mod
├── go.sum
└── Dockerfile    — multi-stage (golang:1.22-alpine → alpine:3.19)

web/              — Next.js static export output (deployed to GitHub Pages)

agents/           — git submodule: AI Teammate workflows

.github/
├── workflows/
│   ├── ai-teammate.yml   — AI agent workflow
│   ├── deploy-api.yml    — Build → GCR → Cloud Run
│   └── deploy-pages.yml  — web/ → GitHub Pages
└── actions/
    └── setup-java-only/  — reusable Java + Gradle cache action
```

## CI/CD Credentials

### GCP Authentication

`GCP_SA_KEY` (secret) contains the full JSON key for the deployment service account. Authenticate in GitHub Actions workflows with:

```yaml
- uses: google-github-actions/auth@v2
  with:
    credentials_json: ${{ secrets.GCP_SA_KEY }}
- uses: google-github-actions/setup-gcloud@v2
```

This sets up Application Default Credentials (ADC) automatically — the `GOOGLE_APPLICATION_CREDENTIALS` env var is available to all subsequent steps. **No additional GCP secret is needed for tests** — `GCP_SA_KEY` + `GCP_PROJECT_ID` (variable) is sufficient.

`GCP_AI_TEAMMATE_SA_KEY` (secret) is a separate read-only service account key used by the AI Teammate agent for GCP inspection (not for deployments).

### Firebase Test Credentials

For integration tests requiring a real Firebase ID token, store a dedicated test user in secrets and generate the token at CI runtime (tokens expire in 1 hour — never store them as secrets):

```yaml
- name: Get Firebase test token
  run: |
    RESP=$(curl -s -X POST \
      "https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key=${{ vars.FIREBASE_API_KEY }}" \
      -H "Content-Type: application/json" \
      -d '{"email":"${{ secrets.FIREBASE_TEST_EMAIL }}","password":"${{ secrets.FIREBASE_TEST_PASSWORD }}","returnSecureToken":true}')
    echo "FIREBASE_TEST_TOKEN=$(echo $RESP | jq -r .idToken)" >> $GITHUB_ENV
    echo "FIREBASE_TEST_UID=$(echo $RESP | jq -r .localId)" >> $GITHUB_ENV
    echo "FIREBASE_TEST_EMAIL=${{ secrets.FIREBASE_TEST_EMAIL }}" >> $GITHUB_ENV
```

Required secrets (not yet added): `FIREBASE_TEST_EMAIL`, `FIREBASE_TEST_PASSWORD` — a dedicated Firebase test user account for project `ai-native-478811`.

### Managing Secrets and Variables

Agents with access to the `gh` CLI can add repo-level secrets and variables. They are available to **all** workflows (`ai-teammate.yml`, `deploy-api.yml`, `deploy-pages.yml`, `unit-tests.yml`):

```bash
# Check what already exists (never overwrite without checking first)
gh secret list --repo ai-teammate/mytube
gh variable list --repo ai-teammate/mytube

# Add a non-sensitive variable
gh variable set VAR_NAME --body "value" --repo ai-teammate/mytube

# Sensitive secrets cannot be set automatically (no value available) —
# document them in outputs/response.md as "Human action required"
```

**Always update the tables below** when adding new secrets or variables.

## Infrastructure Inspection

The AI Teammate service account has **read-only GCP access**. Agents can use the `gcloud` CLI to inspect live infrastructure when needed for analysis, debugging, or understanding the current deployment state.

### Available read commands (examples)

```bash
# Cloud Run
gcloud run services describe mytube-api --region=us-central1
gcloud run services list --region=us-central1
gcloud run revisions list --service=mytube-api --region=us-central1

# Cloud SQL
gcloud sql instances list
gcloud sql databases list --instance=<instance-name>

# Google Cloud Storage
gcloud storage buckets list
gcloud storage ls gs://<bucket-name>/

# Secret Manager (list only — values are not readable)
gcloud secrets list

# IAM
gcloud projects get-iam-policy <project-id>
```

> **Read-only**: The service account cannot create, update, or delete any GCP resources. Use `gcloud` only for inspection and diagnostics.

## Configuration

All environment-specific values live in `dmtools.env` (gitignored) and are provisioned to GitHub via `./setup-github.sh`.

### GitHub Secrets

| Secret | Description |
|--------|-------------|
| `GCP_SA_KEY` | GCP service account JSON key for deployments (used via `google-github-actions/auth@v2`) |
| `GCP_AI_TEAMMATE_SA_KEY` | Read-only GCP service account key for AI Teammate infrastructure inspection |
| `DB_USER` | PostgreSQL user |
| `DB_PASSWORD` | PostgreSQL password |
| `PAT_TOKEN` | GitHub PAT (submodule checkout + PR creation) |
| `CURSOR_API_KEY` | Cursor AI agent |
| `JIRA_API_TOKEN` | Jira API |
| `GEMINI_API_KEY` | Gemini AI |
| `FIGMA_TOKEN` | Figma |
| `CODEMIE_API_KEY` | Codemie AI agent |
| `FIREBASE_TEST_EMAIL` | ⚠️ **Not yet added** — email of dedicated Firebase test user for integration tests |
| `FIREBASE_TEST_PASSWORD` | ⚠️ **Not yet added** — password of dedicated Firebase test user for integration tests |

### GitHub Variables

| Variable | Description |
|----------|-------------|
| `GCP_PROJECT_ID` | GCP project ID |
| `GCP_REGION` | GCP region |
| `CLOUD_SQL_CONNECTION_NAME` | Cloud SQL instance connection name |
| `DB_NAME` | Database name |
| `GCP_DB_USER_SECRET` | Secret Manager secret name for DB user |
| `GCP_DB_PASSWORD_SECRET` | Secret Manager secret name for DB password |
| `FIREBASE_PROJECT_ID` | Firebase project ID |
| `FIREBASE_API_KEY` | Firebase web API key (public) |
| `RAW_OBJECT_PATH` | Path to test video in raw uploads bucket (e.g. `test-videos/test_video.mp4`) — used by transcoder integration tests |
| `FIREBASE_AUTH_DOMAIN` | Firebase auth domain |
| `FIREBASE_MESSAGING_SENDER_ID` | Firebase messaging sender ID |
| `FIREBASE_APP_ID` | Firebase web app ID |
| `FIREBASE_STORAGE_BUCKET` | Firebase storage bucket |
| `JIRA_BASE_PATH` | Jira instance URL |
| `JIRA_AUTH_TYPE` | Jira auth type |
| `AI_AGENT_PROVIDER` | AI agent provider (`cursor` or `codemie`) |
| `CODEMIE_BASE_URL` | Codemie endpoint |
| `CODEMIE_MODEL` | Codemie model name |
| `CODEMIE_MAX_TURNS` | Codemie max turns |