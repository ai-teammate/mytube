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

## Configuration

All environment-specific values live in `dmtools.env` (gitignored) and are provisioned to GitHub via `./setup-github.sh`.

### GitHub Secrets

| Secret | Description |
|--------|-------------|
| `GCP_SA_KEY` | GCP service account JSON key for deployments |
| `DB_USER` | PostgreSQL user |
| `DB_PASSWORD` | PostgreSQL password |
| `PAT_TOKEN` | GitHub PAT (submodule checkout + PR creation) |
| `CURSOR_API_KEY` | Cursor AI agent |
| `JIRA_API_TOKEN` | Jira API |
| `GEMINI_API_KEY` | Gemini AI |
| `FIGMA_TOKEN` | Figma |
| `CODEMIE_API_KEY` | Codemie AI agent |

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