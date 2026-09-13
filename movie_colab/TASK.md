# Antigravity Implementation Checklist

## Phase 1: Environment & Container Initialization
- [x] Create repository folder structure (`/frontend` and `/backend`)
- [x] Write `/backend/Dockerfile` (Python 3.11-slim, aria2, yt-dlp, ffmpeg, curl)
- [x] Create `/backend/requirements.txt` (fastapi, uvicorn, httpx, pydantic>=2, pydantic-settings, anyio)
- [x] Configure `docker-compose.yml` (backend:8000 hot-reload, frontend:3000 node:20)

## Phase 2: Backend Streaming Engine (`/backend`)
- [x] Implement `schemas/transfer.py` (TransferRequest, TransferStatus enum, ProgressEvent, TransferStartResponse)
- [x] Build `core/drive_uploader.py`
  - [x] Folder resolution logic (walk/create nested path under drive.file scope)
  - [x] Drive resumable upload session initializer (POST uploadType=resumable)
  - [x] Resumable chunked PUT streamer (16 MB ChunkAccumulator, 256 KiB aligned)
  - [x] Forced kernel cache sync hook (os.sync() on 200/201 from Drive)
- [x] Build `core/downloader.py`
  - [x] Primary: httpx.AsyncClient streaming with asyncio.Queue producer/consumer
  - [x] Fallback: yt-dlp subprocess piping to stdout for media platforms / httpx failures
- [x] Implement `core/telemetry.py`
  - [x] In-memory asyncio.Queue registry mapping task_id -> subscriber queues
  - [x] Status progression: queued -> downloading -> uploading_to_drive -> syncing -> completed/failed
  - [x] 30s SSE heartbeat comment to keep connections alive
- [x] Wire API routes in `api/v1/endpoints.py`
  - [x] `POST /api/v1/transfer/start` (asyncio.create_task background pipeline)
  - [x] `GET /api/v1/transfer/{task_id}/progress` (StreamingResponse SSE)
  - [x] `POST /api/v1/transfer/{task_id}/cancel` (cancel event set)

## Phase 3: Frontend Dashboard & Authentication (`/frontend`)
- [x] Initialize Next.js 14 project with Tailwind CSS and App Router
- [x] Install and wrap root layout with `@react-oauth/google` (via GoogleOAuthProviderWrapper)
- [x] Build `components/AuthButton.tsx`
  - [x] useGoogleLogin({ flow: 'implicit', scope: 'drive.file' })
  - [x] Fetches userinfo email after login; shows session badge
- [x] Build `components/DownloadForm.tsx`
  - [x] URL input + paste handler with filename inference
  - [x] Folder path input (default: Downloads/movie colab)
  - [x] Filename override input
  - [x] Submit -> startTransfer() -> SSE task_id
- [x] Build `components/ProgressBar.tsx`
  - [x] EventSource connected to /api/v1/transfer/{task_id}/progress
  - [x] Animated progress bar, bytes downloaded, bytes uploaded, phase label
- [x] Build `components/CompletionAlert.tsx`
  - [x] AudioContext synthetic ping on success
  - [x] Drive file link on completion

## Phase 4: Local Verification & Integration
- [x] Run backend FastAPI server on port 8000
- [x] Run frontend Next.js server on port 3000
- [x] Test CORS preflight between ports 3000 and 8000
- [x] Execute dry-run test with public file URL
- [x] Verify error boundaries (invalid URL, expired token, cancel mid-transfer)