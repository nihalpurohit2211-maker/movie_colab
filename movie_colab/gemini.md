# Direct-to-Drive Cloud Ingestion Engine

## 1. System Mission & Core Constraints
This application allows authenticated users to input any downloadable file URL, video link, or direct link on a web client and transfer it directly into their personal Google Drive without consuming local device storage or manual Google Colab execution.

### Non-Negotiable Constraints
- **Zero Full-File Disk Footprint:** Worker nodes run on resource-constrained containers (512MB RAM, limited ephemeral storage). The ingestion pipeline MUST NOT accumulate entire multi-gigabyte files locally before uploading.
- **Chunked Resumable Ingestion:** Data streams from the source directly into Google Drive using the Drive REST API v3 resumable upload protocol (`uploadType=resumable`) with 16MB or 64MB chunks.
- **Strict Scope Boundaries:** Authentication is strictly scoped to `https://www.googleapis.com/auth/drive.file`. The app must never request broad access to preexisting user files.
- **OS-Level Sync:** Every completed write must execute an operating system cache flush (`os.sync()`) before emitting the terminal completion state.

---

## 2. Technology Stack & Architecture

### Frontend (`/frontend`)
- **Framework:** Next.js 14+ (App Router), TypeScript (strict mode).
- **Styling:** Tailwind CSS, Lucide React icons.
- **Authentication:** `@react-oauth/google` requesting access token with scope `https://www.googleapis.com/auth/drive.file`.
- **Live Telemetry:** Native `EventSource` listening to backend Server-Sent Events (SSE).

### Backend Worker (`/backend`)
- **Runtime:** Python 3.11+ with FastAPI & Uvicorn.
- **Data Validation:** Pydantic v2 schemas.
- **Ingestion Core:** 
  - Primary: `aria2c` optimized flags: `-x 1 -s 1 --file-allocation=none --disk-cache=128M`.
  - Fallback: `yt-dlp` for media sites / tokenized stream manifests.
  - Pipe: Python generator streaming chunks directly into the Google Drive upload URI.
- **Telemetric Engine:** In-memory `asyncio.Queue` registry mapping `task_id` to live transfer metrics.

---

## 3. Directory Layout
```text
.
├── GEMINI.md
├── TASK.md
├── docker-compose.yml
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── app/
│   │   ├── main.py
│   │   ├── config.py
│   │   ├── api/
│   │   │   └── v1/
│   │   │       ├── router.py
│   │   │       └── endpoints.py
│   │   ├── core/
│   │   │   ├── drive_uploader.py
│   │   │   ├── downloader.py
│   │   │   └── telemetry.py
│   │   └── schemas/
│   │       └── transfer.py
│   └── tests/
└── frontend/
    ├── package.json
    ├── tailwind.config.ts
    ├── src/
    │   ├── app/
    │   │   ├── layout.tsx
    │   │   └── page.tsx
    │   ├── components/
    │   │   ├── AuthButton.tsx
    │   │   ├── DownloadForm.tsx
    │   │   ├── ProgressBar.tsx
    │   │   └── CompletionAlert.tsx
    │   └── lib/
    │       └── api.ts