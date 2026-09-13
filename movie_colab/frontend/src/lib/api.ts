/**
 * lib/api.ts
 * Typed wrappers around the backend transfer API and SSE stream.
 */

const API_BASE = (
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"
).replace(/\/+$/, "");

// ── Types ──────────────────────────────────────────────────────────────────

export type TransferStatus =
  | "queued"
  | "downloading"
  | "uploading_to_drive"
  | "syncing"
  | "completed"
  | "failed";

export interface ProgressEvent {
  task_id: string;
  status: TransferStatus;
  bytes_downloaded: number;
  bytes_uploaded: number;
  total_bytes: number;
  percent: number;
  message: string;
  speed_bytes_per_sec?: number;
  eta_seconds?: number;
  drive_file_id?: string;
  drive_file_link?: string;
  error?: string;
}

export interface StartTransferPayload {
  url: string;
  access_token: string;
  folder_name: string;
  filename?: string;
}

// ── API helpers ────────────────────────────────────────────────────────────

export async function startTransfer(
  payload: StartTransferPayload
): Promise<{ task_id: string }> {
  const resp = await fetch(`${API_BASE}/api/v1/transfer/start`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  if (!resp.ok) {
    let detail = `HTTP ${resp.status}`;
    try {
      const body = (await resp.json()) as { detail?: string; message?: string };
      detail = body.detail ?? body.message ?? detail;
    } catch {
      /* ignore */
    }
    throw new Error(detail);
  }

  return resp.json() as Promise<{ task_id: string }>;
}

/**
 * Fetch snapshot of a task status. Used for mobile background recovery and reconnection polling.
 */
export async function getTransferStatus(taskId: string): Promise<ProgressEvent> {
  const resp = await fetch(`${API_BASE}/api/v1/transfer/${taskId}/status`);
  if (!resp.ok) {
    throw new Error(`Failed to fetch status: HTTP ${resp.status}`);
  }
  return resp.json() as Promise<ProgressEvent>;
}

/**
 * Open an EventSource connection to the SSE progress stream.
 * The caller is responsible for closing it when done.
 */
export function openProgressStream(taskId: string): EventSource {
  return new EventSource(
    `${API_BASE}/api/v1/transfer/${taskId}/progress`
  );
}

export async function cancelTransfer(taskId: string): Promise<void> {
  await fetch(`${API_BASE}/api/v1/transfer/${taskId}/cancel`, {
    method: "POST",
  });
}
