# Direct-to-Drive Cloud Ingestion Engine - Build Walkthrough

## What Was Built

A full-stack web application that streams any URL directly into Google Drive via chunked
resumable uploads -- with **zero full-file disk footprint**.

---

## Repository Structure

```
movie_colab/
├── GEMINI.md                        # Architecture constraints
├── TASK.md                          # Implementation checklist (all complete)
├── docker-compose.yml               # Backend :8000 + Frontend :3000
├── walkthrough.md                   # Full implementation walkthrough
├── backend/
│   ├── Dockerfile                   # Python 3.11-slim, aria2, ffmpeg, yt-dlp
│   ├── requirements.txt
│   └── app/
│       ├── main.py                  # FastAPI app factory + CORS
│       ├── config.py                # Pydantic BaseSettings
│       ├── api/v1/
│       │   ├── router.py
│       │   └── endpoints.py         # POST /start  GET /progress  POST /cancel
│       ├── core/
│       │   ├── downloader.py        # httpx primary / yt-dlp fallback
│       │   ├── drive_uploader.py    # 16 MB ChunkAccumulator + os.sync()
│       │   └── telemetry.py         # asyncio.Queue SSE fan-out registry
│       └── schemas/
│           └── transfer.py          # Pydantic v2 models
└── frontend/
    ├── package.json                 # Next.js 14, @react-oauth/google, Tailwind
    ├── next.config.mjs
    ├── tailwind.config.ts
    └── src/
        ├── app/
        │   ├── layout.tsx           # Root layout + GoogleOAuthProviderWrapper
        │   └── page.tsx             # Main page: auth + form + progress + alert
        ├── components/
        │   ├── AuthButton.tsx       # useGoogleLogin implicit flow
        │   ├── DownloadForm.tsx     # URL / folder / filename inputs
        │   ├── ProgressBar.tsx      # Live SSE progress bar with shimmer
        │   └── CompletionAlert.tsx  # Audio ping + Drive file link
        └── lib/
            └── api.ts               # startTransfer / openProgressStream / cancel
```

---

## Phase 1 - Environment

| File | Purpose |
|---|---|
| `docker-compose.yml` | Backend hot-reload on :8000, Frontend node:20 on :3000 |
| `backend/Dockerfile` | Python 3.11-slim + aria2 + ffmpeg + yt-dlp binary (latest) |
| `backend/requirements.txt` | fastapi, uvicorn, httpx, pydantic>=2, pydantic-settings, anyio |

---

## Phase 2 - Backend Streaming Engine

### Pipeline flow

```
POST /api/v1/transfer/start
  => asyncio.create_task(_run_transfer)
        => downloader.open_stream(url)
             PRIMARY: httpx.AsyncClient.stream() -> asyncio.Queue -> generator
             FALLBACK: yt-dlp -o - subprocess -> asyncio.Queue -> generator
        => drive_uploader.resolve_or_create_folder()   walk/create nested path
        => drive_uploader.initiate_resumable_session() POST uploadType=resumable
        => drive_uploader.stream_to_drive()
             ChunkAccumulator: buffer until 16 MB (64 x 256 KiB)
             PUT chunk with Content-Range header
             308 -> continue  |  200/201 -> os.sync() then return file_id
             telemetry.emit() progress events at each chunk

GET  /api/v1/transfer/{id}/progress  -> StreamingResponse text/event-stream
POST /api/v1/transfer/{id}/cancel    -> cancel_event.set()
```

### Non-negotiable constraints enforced

| Constraint | Where enforced |
|---|---|
| Zero full-file disk footprint | httpx streams via asyncio.Queue; yt-dlp pipes stdout; nothing hits disk |
| 16 MB aligned chunks | ChunkAccumulator in drive_uploader.py: every intermediate PUT = exactly 16,777,216 bytes |
| os.sync() before completed event | Called in _put_chunk() on HTTP 200/201, before stream_to_drive returns |
| drive.file scope only | useGoogleLogin scope: https://www.googleapis.com/auth/drive.file |
| SSE heartbeat | 30-second comment frame in telemetry.py keeps connections alive through proxies |

---

## Phase 3 - Frontend Dashboard

### Component tree

```
layout.tsx  (Server Component)
  GoogleOAuthProviderWrapper  [use client boundary]
    page.tsx  (state: accessToken, taskId, progress, isTransferring)
      AuthButton        useGoogleLogin flow=implicit scope=drive.file
      DownloadForm      POST -> /api/v1/transfer/start -> task_id
      ProgressBar       EventSource -> live SSE events -> animated bar
      CompletionAlert   AudioContext ping + Drive link on success
```

### Key design decisions

- **flow: implicit** - browser receives access_token directly in the popup postMessage.
  No server-side authorization-code exchange required.
- **GoogleOAuthProviderWrapper** - dedicated use-client component wraps GoogleOAuthProvider
  so the root layout.tsx can remain a React Server Component.
- **SSE via native EventSource** - no extra library; connects to backend at
  NEXT_PUBLIC_API_URL (default http://localhost:8000) directly from the browser.
- **Audio ping** - AudioContext oscillator (880 Hz to 440 Hz glide) plays on completed event.

---

## Phase 4 - Verification Results

| Test | Result |
|---|---|
| Python AST syntax (14 files) | PASS |
| pip install -r requirements.txt | Exit 0 |
| Module imports (8 modules) | All resolve cleanly |
| /health endpoint | HTTP 200 |
| Routes registered | /start, /{id}/progress, /{id}/cancel |
| CORS preflight | HTTP 200, Access-Control-Allow-Origin: http://localhost:3000 |
| npm install | Exit 0 |
| tsc --noEmit | Zero TypeScript errors |
| next build | Exit 0, compiled, 4/4 static pages generated |

---

## How to Run Locally

### Prerequisites

1. Create a Google Cloud OAuth 2.0 Web Client ID
   at https://console.cloud.google.com/apis/credentials (type: Web Application).
2. Add http://localhost:3000 as an Authorised JavaScript Origin.
3. Copy frontend/.env.local.example to frontend/.env.local and fill in
   NEXT_PUBLIC_GOOGLE_CLIENT_ID=<your-client-id>.

### Option A - Docker Compose

`ash
docker-compose up --build
# Backend  -> http://localhost:8000
# Frontend -> http://localhost:3000
`

### Option B - Native (no Docker)

`ash
# Terminal 1 - Backend
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000

# Terminal 2 - Frontend
cd frontend
cp .env.local.example .env.local
npm install
npm run dev
`

### Usage flow

1. Open http://localhost:3000
2. Click Sign in with Google and approve the drive.file permission popup.
3. Paste any direct-download URL or YouTube/Vimeo link into the URL field.
4. Optionally override the Drive folder path or filename.
5. Click Send to Drive and watch the live SSE progress bar.
6. On completion click Open in Google Drive to verify the file.
