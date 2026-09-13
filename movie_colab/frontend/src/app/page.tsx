"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import AuthButton from "@/components/AuthButton";
import DownloadForm from "@/components/DownloadForm";
import ProgressBar from "@/components/ProgressBar";
import CompletionAlert from "@/components/CompletionAlert";
import { openProgressStream, getTransferStatus, cancelTransfer } from "@/lib/api";
import type { ProgressEvent } from "@/lib/api";

const STORAGE_KEY_TOKEN = "drive_ingest_token";
const STORAGE_KEY_EMAIL = "drive_ingest_email";
const STORAGE_KEY_TASK = "drive_ingest_active_task";

export default function HomePage() {
  const [accessToken, setAccessToken] = useState<string | null>(null);
  const [userEmail, setUserEmail] = useState<string | null>(null);
  const [taskId, setTaskId] = useState<string | null>(null);
  const [progress, setProgress] = useState<ProgressEvent | null>(null);
  const [isTransferring, setIsTransferring] = useState(false);
  const eventSourceRef = useRef<EventSource | null>(null);
  const retryTimeoutRef = useRef<NodeJS.Timeout | null>(null);

  // ── 1. Restore persistent login and active task from localStorage on mount ──
  useEffect(() => {
    if (typeof window === "undefined") return;

    try {
      const savedToken = localStorage.getItem(STORAGE_KEY_TOKEN);
      const savedEmail = localStorage.getItem(STORAGE_KEY_EMAIL);
      const savedTask = localStorage.getItem(STORAGE_KEY_TASK);

      if (savedToken) {
        setAccessToken(savedToken);
        setUserEmail(savedEmail ?? null);
      }

      if (savedTask) {
        setTaskId(savedTask);
        setIsTransferring(true);
        // Immediately fetch snapshot in case it already completed while away
        getTransferStatus(savedTask)
          .then((status) => {
            setProgress(status);
            if (status.status === "completed" || status.status === "failed") {
              setIsTransferring(false);
              localStorage.removeItem(STORAGE_KEY_TASK);
            }
          })
          .catch(() => {
            /* status might not be found if pruned */
          });
      }
    } catch {
      /* localStorage may be unavailable in private browsing */
    }
  }, []);

  // ── 2. Request Notification permission for background alert ──
  const requestNotificationPermission = useCallback(() => {
    if (typeof window !== "undefined" && "Notification" in window) {
      if (Notification.permission === "default") {
        Notification.requestPermission().catch(() => {});
      }
    }
  }, []);

  const fireCompletionNotification = useCallback((message: string) => {
    if (
      typeof window !== "undefined" &&
      "Notification" in window &&
      Notification.permission === "granted" &&
      document.visibilityState !== "visible"
    ) {
      try {
        new Notification("Transfer to Google Drive Complete! ☁️", {
          body: message || "Your file is ready in Google Drive.",
          icon: "/favicon.ico",
        });
      } catch {
        /* ignore mobile browser restriction */
      }
    }
  }, []);

  // ── 3. Wire SSE progress stream with auto-reconnection and visibility recovery ──
  const connectSSE = useCallback(
    (currentTaskId: string) => {
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
      }

      const es = openProgressStream(currentTaskId);
      eventSourceRef.current = es;

      es.onmessage = (event: MessageEvent) => {
        try {
          const data = JSON.parse(event.data as string) as ProgressEvent;
          setProgress(data);

          if (data.status === "completed" || data.status === "failed") {
            es.close();
            setIsTransferring(false);
            try {
              localStorage.removeItem(STORAGE_KEY_TASK);
            } catch {}

            if (data.status === "completed") {
              fireCompletionNotification(data.message);
            }
          }
        } catch {
          /* ignore JSON parse error */
        }
      };

      es.onerror = () => {
        // Do NOT immediately mark failed or abort. Mobile browsers often drop SSE when backgrounded.
        es.close();

        // Check backend status via REST polling fallback
        getTransferStatus(currentTaskId)
          .then((snapshot) => {
            setProgress(snapshot);
            if (snapshot.status === "completed" || snapshot.status === "failed") {
              setIsTransferring(false);
              try {
                localStorage.removeItem(STORAGE_KEY_TASK);
              } catch {}
              if (snapshot.status === "completed") {
                fireCompletionNotification(snapshot.message);
              }
              return;
            }

            // Still running — retry SSE connection after backoff
            if (retryTimeoutRef.current) clearTimeout(retryTimeoutRef.current);
            retryTimeoutRef.current = setTimeout(() => {
              if (isTransferring || currentTaskId === taskId) {
                connectSSE(currentTaskId);
              }
            }, 2500);
          })
          .catch(() => {
            // Task might have finished or server temporarily unreachable; retry
            if (retryTimeoutRef.current) clearTimeout(retryTimeoutRef.current);
            retryTimeoutRef.current = setTimeout(() => {
              connectSSE(currentTaskId);
            }, 3000);
          });
      };
    },
    [isTransferring, taskId, fireCompletionNotification]
  );

  useEffect(() => {
    if (!taskId) return;

    connectSSE(taskId);

    // Reconnection triggers for mobile Android / background tab wake-up
    const handleVisibilityChange = () => {
      if (document.visibilityState === "visible" && taskId) {
        getTransferStatus(taskId)
          .then((status) => {
            setProgress(status);
            if (status.status === "completed" || status.status === "failed") {
              setIsTransferring(false);
              localStorage.removeItem(STORAGE_KEY_TASK);
            } else if (!eventSourceRef.current || eventSourceRef.current.readyState === EventSource.CLOSED) {
              connectSSE(taskId);
            }
          })
          .catch(() => {});
      }
    };

    const handleOnline = () => {
      if (taskId) {
        connectSSE(taskId);
      }
    };

    document.addEventListener("visibilitychange", handleVisibilityChange);
    window.addEventListener("online", handleOnline);

    return () => {
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
      }
      if (retryTimeoutRef.current) {
        clearTimeout(retryTimeoutRef.current);
      }
      document.removeEventListener("visibilitychange", handleVisibilityChange);
      window.removeEventListener("online", handleOnline);
    };
  }, [taskId, connectSSE]);

  // ── 4. Form Action Handlers ──
  const handleTransferStart = useCallback(
    (newTaskId: string) => {
      setTaskId(newTaskId);
      setProgress(null);
      setIsTransferring(true);
      requestNotificationPermission();

      try {
        localStorage.setItem(STORAGE_KEY_TASK, newTaskId);
      } catch {}
    },
    [requestNotificationPermission]
  );

  const handleCancel = useCallback(async () => {
    if (taskId) {
      try {
        await cancelTransfer(taskId);
      } catch {
        /* ignore */
      }
      setIsTransferring(false);
      try {
        localStorage.removeItem(STORAGE_KEY_TASK);
      } catch {}
    }
  }, [taskId]);

  const handleLogin = useCallback((token: string, email?: string) => {
    setAccessToken(token);
    setUserEmail(email ?? null);
    try {
      localStorage.setItem(STORAGE_KEY_TOKEN, token);
      if (email) {
        localStorage.setItem(STORAGE_KEY_EMAIL, email);
      }
    } catch {}
  }, []);

  const handleLogout = useCallback(() => {
    setAccessToken(null);
    setUserEmail(null);
    setTaskId(null);
    setProgress(null);
    setIsTransferring(false);
    try {
      localStorage.removeItem(STORAGE_KEY_TOKEN);
      localStorage.removeItem(STORAGE_KEY_EMAIL);
      localStorage.removeItem(STORAGE_KEY_TASK);
    } catch {}
  }, []);

  const handleDismiss = useCallback(() => {
    setProgress(null);
    setTaskId(null);
    try {
      localStorage.removeItem(STORAGE_KEY_TASK);
    } catch {}
  }, []);

  const isTerminal =
    progress?.status === "completed" || progress?.status === "failed";

  return (
    <main className="min-h-screen bg-gradient-to-br from-slate-900 via-blue-950 to-slate-900 flex flex-col items-center justify-start p-6 sm:p-10">
      <div className="w-full max-w-2xl space-y-6">
        {/* ── Header ── */}
        <div className="text-center space-y-2 pt-6">
          <h1 className="text-4xl font-bold text-white tracking-tight">
            ☁️ Drive Ingestion Engine
          </h1>
          <p className="text-slate-400 text-sm max-w-md mx-auto">
            Paste any URL — direct link or media platform — and stream it
            straight into Google Drive. Zero local storage consumed.
          </p>
        </div>

        {/* ── Auth ── */}
        <div className="flex justify-center">
          <AuthButton
            onLogin={handleLogin}
            onLogout={handleLogout}
            isAuthenticated={!!accessToken}
            userEmail={userEmail ?? undefined}
          />
        </div>

        {/* ── Download form (only when authenticated) ── */}
        {accessToken && (
          <DownloadForm
            accessToken={accessToken}
            isTransferring={isTransferring}
            onTransferStart={handleTransferStart}
            onCancel={handleCancel}
          />
        )}

        {/* ── Live progress ── */}
        {progress && !isTerminal && <ProgressBar progress={progress} />}

        {/* ── Completion / failure alert ── */}
        {progress && isTerminal && (
          <CompletionAlert progress={progress} onDismiss={handleDismiss} />
        )}
      </div>
    </main>
  );
}
