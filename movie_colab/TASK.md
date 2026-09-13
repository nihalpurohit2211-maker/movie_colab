---

### File 2: `TASK.md`

Save this at the root of your project:

```markdown
# Antigravity Implementation Checklist

- [ ] **Phase 1: Environment & Container Initialization**
  - [ ] Create repository folder structure (`/frontend` and `/backend`).
  - [ ] Write `/backend/Dockerfile` installing Python 3.11, `aria2`, `yt-dlp`, and `curl`.
  - [ ] Create `/backend/requirements.txt` (`fastapi`, `uvicorn`, `httpx`, `requests`, `pydantic>=2.0`).
  - [ ] Configure `docker-compose.yml` for local multi-service testing.

- [ ] **Phase 2: Backend Streaming Engine (`/backend`)**
  - [ ] Implement `schemas/transfer.py` for request validation (`url`, `access_token`, `folder_name`, `filename`).
  - [ ] Build `core/drive_uploader.py`:
    - [ ] Folder resolution logic (find or create folder in user Drive).
    - [ ] Drive resumable upload session initializer.
    - [ ] Resumable chunked `PUT` streamer (16MB buffer).
    - [ ] Forced kernel cache sync hook (`os.sync()`).
  - [ ] Build `core/downloader.py`:
    - [ ] Source stream generator using `httpx` / `aria2c` optimized flags (`-x 1 -s 1 --disk-cache=128M`).
    - [ ] Fallback execution for `yt-dlp` upon direct stream rejection.
  - [ ] Implement `core/telemetry.py`:
    - [ ] In-memory event registry mapping `task_id` to transfer status.
    - [ ] Status progression: `queued` -> `downloading` -> `uploading_to_drive` -> `syncing` -> `completed` / `failed`.
  - [ ] Wire API routes in `api/v1/endpoints.py`:
    - [ ] `POST /api/v1/transfer/start`: Spawns async streaming background task, returns `task_id`.
    - [ ] `GET /api/v1/transfer/{task_id}/progress`: Streams real-time SSE metrics.
    - [ ] `POST /api/v1/transfer/{task_id}/cancel`: Aborts active stream.

- [ ] **Phase 3: Frontend Dashboard & Authentication (`/frontend`)**
  - [ ] Initialize Next.js 14 project with Tailwind CSS and App Router.
  - [ ] Install and wrap root layout with `@react-oauth/google`.
  - [ ] Build `components/AuthButton.tsx`:
    - [ ] One-click Google Login requesting scope `https://www.googleapis.com/auth/drive.file`.
    - [ ] Session badge displaying authenticated user state.
  - [ ] Build `components/DownloadForm.tsx`:
    - [ ] URL input field with paste handler.
    - [ ] Folder input field with default `Downloads/movie colab`.
    - [ ] File name override field.
    - [ ] Trigger button sending payload to backend `/api/v1/transfer/start`.
  - [ ] Build `components/ProgressBar.tsx` & `components/CompletionAlert.tsx`:
    - [ ] Dynamic connection to SSE endpoint `/api/v1/transfer/{task_id}/progress`.
    - [ ] Visual progress percentage, transferred bytes, and transfer phase.
    - [ ] Completion badge with audible completion ping or alert notification.

- [ ] **Phase 4: Local Verification & Integration**
  - [ ] Run backend FastAPI server on port 8000.
  - [ ] Run frontend Next.js server on port 3000.
  - [ ] Test CORS preflight and headers between ports.
  - [ ] Execute dry-run test using a public test file URL to verify chunk generator and telemetry stream.
  - [ ] Verify error boundaries: test invalid URL, expired token, and network interruption.