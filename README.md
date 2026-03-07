# Архитектура проекта mytube

Кратко:
- Frontend: /web — Next.js 16 + React 19, Tailwind, video.js, Firebase (клиент). Деплой: GitHub Pages (static export).
- Backend: /api — Go 1.24, Dockerfile, развернут на Cloud Run через GitHub Actions; использует Cloud SQL (Postgres) и GCS.
- Транскодер: /api/cmd/transcoder + infra/transcoder-trigger — FFmpeg в контейнере, выполняется как Cloud Run Job, запускается Eventarc -> Trigger.
- Хранение видео: GCS — RAW_UPLOADS_BUCKET (private) для исходников, HLS_BUCKET (public) для HLS/плейлистов (CDN_BASE_URL).
- Авторизация: Firebase Auth (клиент SDK в /web, серверная проверка в /api через auth.NewFirebaseVerifier).
- CI/CD и infra: .github/workflows (deploy-api, deploy-transcoder-trigger, deploy-pages), infra/setup.sh, cloudjobs.yaml.

> Текста минимум — ниже в основном диаграммы mermaid.

---

## Схема: общая архитектура

```mermaid
flowchart LR
  subgraph Client
    U[Пользователь]
  end
  U --> Browser[Next.js (web/) — GitHub Pages]
  Browser -->|ID Token| Firebase[Firebase Auth]
  Browser -->|REST (JWT)| API[API — Go (Cloud Run)]
  API -->|signed URLs| GCS_RAW[GCS: RAW_UPLOADS_BUCKET (private)]
  GCS_RAW -->|object.finalize| Eventarc[Eventarc]
  Eventarc --> Trigger[Transcoder Trigger (Cloud Run)]
  Trigger -->|start job| Transcoder[Transcoder Job (Cloud Run Job, FFmpeg)]
  Transcoder --> GCS_HLS[GCS: HLS_BUCKET (public)]
  Transcoder --> DB[(Postgres — Cloud SQL)]
  API --> DB
  API --> GCS_HLS
  GitHubActions[GitHub Actions] -->|deploy| API
  GitHubActions -->|deploy| Trigger
  GitHubActions -->|deploy| Pages[GitHub Pages (web/out)]
```

---

## Развёртывание (где что работает)

```mermaid
graph TB
  subgraph "Google Cloud Platform"
    direction TB
    CloudRunAPI[Cloud Run — mytube-api]
    CloudRunTrigger[Cloud Run — mytube-transcoder-trigger]
    CloudRunJob[Cloud Run Job — mytube-transcoder]
    GCS_RAW[Cloud Storage — mytube-raw-uploads]
    GCS_HLS[Cloud Storage — mytube-hls-output (public)]
    CloudSQL[(Cloud SQL — Postgres)]
    Eventarc[Eventarc]
    SecretManager[Secret Manager]
  end
  subgraph "CI/CD"
    GHActions[.github/workflows]
    GCR[gcr.io (container registry)]
    Pages[GitHub Pages]
  end
  GHActions --> GCR
  GHActions --> CloudRunAPI
  GHActions --> CloudRunTrigger
  GHActions --> Pages
  CloudRunAPI --> CloudSQL
  CloudRunAPI --> GCS_RAW
  CloudRunAPI --> GCS_HLS
  GCS_RAW --> Eventarc --> CloudRunTrigger --> CloudRunJob --> GCS_HLS
  CloudRunJob --> CloudSQL
  SecretManager -->|DB creds| CloudRunAPI
  SecretManager -->|DB creds| CloudRunJob
```

---

## Поток загрузки и транскодирования (upload → transcode → HLS)

```mermaid
sequenceDiagram
  participant User as User (browser)
  participant Web as Web (Next.js)
  participant API as API (Go)
  participant GCS as GCS RAW_BUCKET
  participant Eventarc as Eventarc
  participant Trigger as Trigger (Cloud Run)
  participant Job as Transcoder Job
  participant HLS as GCS HLS_BUCKET
  participant DB as Postgres (Cloud SQL)

  User->>Web: Login (Firebase SDK) → ID token
  Web->>API: POST /api/videos (Authorization: Bearer ID_TOKEN)
  API->>API: Verify ID token via Firebase Verifier
  API->>DB: Create video DB row (pending)
  API->>API: Sign PUT URL (GCSSigner) for RAW_BUCKET
  API->>Web: Return signed PUT URL
  Web->>GCS: PUT upload to RAW_BUCKET (direct)
  GCS->>Eventarc: object.finalize (gs://RAW_BUCKET/...)
  Eventarc->>Trigger: Invoke trigger service
  Trigger->>Job: Start Cloud Run Job (override RAW_OBJECT_PATH)
  Job->>Job: Transcode (ffmpeg) → write HLS to HLS_BUCKET
  Job->>DB: Update video row (ready + HLS URLs)
  Web->>API: GET /api/videos/{id} (show processed video)
```

---

## Структура репозитория (коротко)

```mermaid
flowchart LR
  repo[Repository root]
  repo --> web["/web — Next.js, React, Tailwind, video.js, firebase (client)"]
  repo --> api["/api — Go 1.24, handlers, repository, storage, Dockerfile, migrations"]
  repo --> transcoder["/api/cmd/transcoder — FFmpeg-enabled binary + Dockerfile"]
  repo --> infra["/infra — setup.sh, cloudjobs.yaml, transcoder-trigger (Cloud Run service)"]
  repo --> workflows["/.github/workflows — deploy-api, deploy-transcoder-trigger, deploy-pages"]
```

---

Файлы для подробностей:
- web/package.json — фронтенд зависимости (Next.js, React, Firebase, video.js, Tailwind)
- api/main.go — вход в API (Firebase verifier, GCS signer, маршруты)
- api/internal/storage/gcs.go — генерация signed PUT URL (GCSSigner)
- infra/setup.sh, infra/cloudjobs.yaml — инструкции по развёртыванию transcoder job и bucket'ов
- .github/workflows/deploy-*.yml — CI/CD: deploy-api (Cloud Run), deploy-transcoder-trigger (Cloud Run), deploy-pages (GitHub Pages)

