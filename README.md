# mytube — Architecture Overview

Short summary:
- Frontend: /web — Next.js 16, React 19, Tailwind CSS, video.js; Firebase client SDK. Deployed as a static export to GitHub Pages via GitHub Actions.
- Backend: /api — Go 1.24, built into a Docker image and deployed to Cloud Run. Uses Cloud SQL (Postgres) and Google Cloud Storage; provides signed upload URLs and verifies Firebase ID tokens server-side.
- Transcoder: /api/cmd/transcoder + infra/transcoder-trigger — FFmpeg in a container; runs as a Cloud Run Job (mytube-transcoder) started by a lightweight trigger service via Eventarc when objects are finalized in the raw uploads bucket.
- Storage: Google Cloud Storage — RAW_UPLOADS_BUCKET (private) for raw uploads, mytube-hls-output (public) for HLS segments/playlists; CDN_BASE_URL used for public delivery.
- Auth: Firebase Authentication (client SDK in /web; server-side verification in /api via auth.NewFirebaseVerifier).
- CI/CD & infra: .github/workflows (deploy-api, deploy-transcoder-trigger, deploy-pages), infra/setup.sh, infra/cloudjobs.yaml.

> Minimal text; most of the README is mermaid diagrams describing the system.

---

## High-level architecture

```mermaid
flowchart LR
  subgraph "Client"
    U["User"]
  end
  U --> Browser["Next.js (web/) — GitHub Pages"]
  Browser -->|"ID Token"| Firebase["Firebase Auth"]
  Browser -->|"REST (Bearer ID Token)"| API["API — Go (Cloud Run)"]
  API -->|"signed URLs"| GCS_RAW["GCS: RAW_UPLOADS_BUCKET (private)"]
  GCS_RAW -->|"object.finalize"| Eventarc["Eventarc"]
  Eventarc --> Trigger["Transcoder Trigger (Cloud Run)"]
  Trigger -->|"start job"| Transcoder["Transcoder Job (Cloud Run Job, FFmpeg)"]
  Transcoder --> GCS_HLS["HLS_BUCKET (public)"]
  Transcoder --> DB["Postgres — Cloud SQL"]
  API --> DB
  API --> GCS_HLS
  GitHubActions["GitHub Actions"] -->|"deploy"| API
  GitHubActions -->|"deploy"| Trigger
  GitHubActions -->|"deploy"| Pages["GitHub Pages"]
  GitHubActions -->|"deploy"| Transcoder
```

---

## Deployment topology (where components run)

```mermaid
graph TB
  subgraph "Google Cloud Platform"
    direction TB
    CloudRunAPI["Cloud Run — mytube-api"]
    CloudRunTrigger["Cloud Run — mytube-transcoder-trigger"]
    CloudRunJob["Cloud Run Job — mytube-transcoder"]
    GCS_RAW["Cloud Storage — mytube-raw-uploads"]
    GCS_HLS["Cloud Storage — mytube-hls-output (public)"]
    CloudSQL["Cloud SQL — Postgres"]
    Eventarc["Eventarc"]
    SecretManager["Secret Manager"]
  end
  subgraph "CI/CD"
    GHActions[".github/workflows"]
    GCR["gcr.io (Container Registry)"]
    Pages["GitHub Pages"]
  end
  GHActions --> GCR
  GHActions --> CloudRunAPI
  GHActions --> CloudRunTrigger
  GHActions --> CloudRunJob
  GHActions --> Pages
  CloudRunAPI --> CloudSQL
  CloudRunAPI --> GCS_RAW
  CloudRunAPI --> GCS_HLS
  GCS_RAW --> Eventarc --> CloudRunTrigger --> CloudRunJob --> GCS_HLS
  CloudRunJob --> CloudSQL
  SecretManager -->|"DB creds"| CloudRunAPI
  SecretManager -->|"DB creds"| CloudRunJob
```

---

## Upload & transcode flow

```mermaid
sequenceDiagram
  participant User as "User (browser)"
  participant Web as "Web (Next.js)"
  participant API as "API (Go)"
  participant GCS as "GCS RAW_BUCKET"
  participant Eventarc as "Eventarc"
  participant Trigger as "Trigger (Cloud Run)"
  participant Job as "Transcoder Job"
  participant HLS as "GCS HLS_BUCKET"
  participant DB as "Postgres (Cloud SQL)"

  User->>Web: Login (Firebase SDK) -> ID token
  Web->>API: POST /api/videos (Authorization: Bearer ID_TOKEN)
  API->>API: Verify ID token via Firebase Verifier
  API->>DB: Create video DB row (status: pending)
  API->>API: Sign PUT URL (GCSSigner) for RAW_BUCKET
  API->>Web: Return signed PUT URL
  Web->>GCS: PUT upload to RAW_BUCKET (direct)
  GCS->>Eventarc: object.finalize (gs://RAW_BUCKET/...)
  Eventarc->>Trigger: Invoke trigger service
  Trigger->>Job: Start Cloud Run Job (override RAW_OBJECT_PATH)
  Job->>Job: Transcode (ffmpeg) -> write HLS to HLS_BUCKET
  Job->>DB: Update video row (status: ready + HLS URLs)
  Web->>API: GET /api/videos/{id} (show processed video)
```

---

## Repository layout (short)

```mermaid
flowchart LR
  repo["Repository root"]
  repo --> web["/web — Next.js, React, Tailwind, video.js, firebase (client)"]
  repo --> api["/api — Go 1.24, handlers, repository, storage, Dockerfile, migrations"]
  repo --> transcoder["/api/cmd/transcoder — FFmpeg-enabled binary + Dockerfile"]
  repo --> infra["/infra — setup.sh, cloudjobs.yaml, transcoder-trigger (Cloud Run service)"]
  repo --> workflows["/.github/workflows — deploy-api, deploy-transcoder-trigger, deploy-pages"]
```

---

Key files to inspect:
- web/package.json — frontend dependencies (Next.js, React, Firebase, video.js, Tailwind)
- api/main.go — API entrypoint (Firebase verifier, GCS signer, route registration)
- api/internal/storage/gcs.go — GCSSigner (signed PUT URL generation)
- infra/setup.sh, infra/cloudjobs.yaml — GCP setup and Cloud Run Job spec
- .github/workflows/deploy-*.yml — CI/CD: deploy-api (Cloud Run), deploy-transcoder-trigger (Cloud Run), deploy-pages (GitHub Pages)

