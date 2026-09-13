# Cloud Deployment Tracker: movie_colab

This live tracker monitors the 4 deployment phases for Render (Backend) and Vercel (Frontend).

---

## 📊 Live Deployment Status

| Phase | Description | Status | Verified Details |
|---|---|---|---|
| **Phase 1** | Repository Structure & Secrets Sanitation | ✅ **COMPLETED** | Root paths verified (`/backend`, `/frontend`), `.gitignore` active, `.env*` untracked, `__pycache__` cleaned |
| **Phase 2** | Backend Deployment (Render / Docker) | 🖡 **READY TO DEPLOY** | Dockerfile updated with dynamic `${PORT:-8000}`, `CHUNK_SIZE_BYTES` flexible validator, CORS ready |
| **Phase 3** | Frontend Deployment (Vercel) | 🖡 **READY TO DEPLOY** | Next.js preset, Root Directory `frontend`, `NEXT_PUBLIC_API_URL` sanitized, Google Client ID ready |
| **Phase 4** | Production Handshake & Security Whitelisting | ⏱ **PENDING URLS** | Add Vercel URL to Google OAuth Authorized Origins & lock Render `ALLOWED_ORIGINS` |

---

## Phase 1: Repository Structure & Sanitation

- [x] **Verify Repository Root Layout**
  - Repository root directly contains `/backend` and `/frontend`.
  - Render Root Directory: `backend`
  - Vercel Root Directory: `frontend`
- [x] **Sanitize Committed Secrets**
  - Added comprehensive root `.gitignore` ignoring `.env*`, `!.env.example`, `!.env.local.example`, `.venv/`, `node_modules/`, `__pycache__/`, `*.tsbuildinfo`.
  - Verified `frontend/.env.local` is ignored and not staged.
  - Purged tracked `.pyc` and `tsbuildinfo` artifacts from git index.

---

## Phase 2: Backend Deployment (Render / Docker)

### Render Configuration
1. Go to [Render Dashboard](https://dashboard.render.com/) -> **New +** -> **Web Service**.
2. Connect your GitHub repository: `nihalpurohit2211-maker/movie_colab`.
3. Configure the service settings:
   - **Name:** `movie-colab-backend` (or your choice)
   - **Region:** `Singapore` (Southeast Asia) or `Frankfurt` (Europe)
   - **Root Directory:** `backend`
   - **Runtime:** `Docker`
   - **Instance Type:** `Free` (or higher)

### Environment Variables on Render
Add these under **Environment Variables** in Render:

| Key | Value | Notes |
|---|---|---|
| `CHUNK_SIZE_BYTES` | `16777216` | 16 MB (64 x 256 KiB) optimized transfer speed under 85 MB RAM ceiling |
| `ALLOWED_ORIGINS` | `*` | Temporary wildcard during initial deployment |
| `APP_ENV` | `production` | Production mode |

- [ ] **Deploy Web Service on Render**
- [ ] **Validate Backend Health**:
  - Once deployed, visit `https://<YOUR_RENDER_BACKEND_URL>/health` -> should return `{"status":"ok"}`.
  - Visit `https://<YOUR_RENDER_BACKEND_URL>/docs` -> opens Swagger UI with `/transfer/start`, `/transfer/{task_id}/progress`, `/transfer/{task_id}/cancel`.

---

## Phase 3: Frontend Deployment (Vercel)

### Vercel Configuration
1. Go to [Vercel Dashboard](https://vercel.com/) -> **Add New...** -> **Project**.
2. Import repository: `nihalpurohit2211-maker/movie_colab`.
3. Configure Project Settings:
   - **Framework Preset:** `Next.js`
   - **Root Directory:** Click **Edit** and select `frontend`.

### Environment Variables on Vercel
Add these under **Environment Variables** in Vercel:

| Key | Value | Notes |
|---|---|---|
| `NEXT_PUBLIC_GOOGLE_CLIENT_ID` | `179818842532-a96o7sheg8hpl1po4lk0q0clae4mlm13.apps.googleusercontent.com` | Google OAuth Client ID |
| `NEXT_PUBLIC_API_URL` | `https://<YOUR_RENDER_BACKEND_URL>` | **No trailing slash** (e.g. `https://movie-colab-backend.onrender.com`) |

- [ ] **Deploy to Vercel**
- [ ] **Verify UI build and deployment**:
  - Inspect build logs for clean compilation.
  - Open Vercel production URL (e.g. `https://movie-colab.vercel.app`).

---

## Phase 4: Production Handshake & Security Whitelisting

- [ ] **Update Google Cloud OAuth Console**:
  1. Open [Google Cloud Console Credentials](https://console.cloud.google.com/apis/credentials).
  2. Click your OAuth 2.0 Web Client ID.
  3. Under **Authorized JavaScript origins**, add your Vercel production URL:
     - `https://<YOUR_APP>.vercel.app`
  4. Click **Save** (allow 2-5 minutes for Google edge CDN propagation).
- [ ] **Lock Down Backend CORS**:
  1. In Render Dashboard -> Environment Variables.
  2. Update `ALLOWED_ORIGINS` from `*` to:
     `https://<YOUR_APP>.vercel.app,http://localhost:3000`
  3. Click **Save Changes** (triggers automatic zero-downtime redeploy).
- [ ] **End-to-End Cloud Transfer Verification**:
  1. Open the production Vercel URL in your browser.
  2. Click **Sign in with Google** and approve `drive.file` scope.
  3. Paste a test URL (e.g. sample video or direct archive).
  4. Click **Send to Drive** and watch real-time SSE progress.
  5. Check Windows Task Manager -> verify local machine has **0% network download usage** while the cloud streams directly to Google Drive.
