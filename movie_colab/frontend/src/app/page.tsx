"use client";

import { useState, useEffect, useCallback } from "react";
import AuthButton from "@/components/AuthButton";
import DownloadForm from "@/components/DownloadForm";
import ProgressBar from "@/components/ProgressBar";
import CompletionAlert from "@/components/CompletionAlert";
import { openProgressStream, cancelTransfer } from "@/lib/api";
import type { ProgressEvent } from "@/lib/api";

export default function HomePage() {
  const [accessToken, setAccessToken] = useState<string | null>(null);
  const [userEmail, setUserEmail] = useState<string | null>(null);
  const [taskId, setTaskId] = useState<string | null>(null);
  const [progress, setProgress] = useState<ProgressEvent | null>(null);
  const [isTransferring, setIsTransferring] = useState(false);

  // Wire SSE stream whenever taskId changes
  useEffect(() => {
    if (!taskId) return;

    const es = openProgressStream(taskId);

    es.onmessage = (event: MessageEvent) => {
      try {
        const data = JSON.parse(event.data as string) as ProgressEvent;
        setProgress(data);
        if (data.status === "completed" || data.status === "failed") {
          es.close();
          setIsTransferring(false);
        }
      } catch {
        /* ignore JSON parse errors */
      }
    };

    es.onerror = () => {
      es.close();
      setIsTransferring(false);
    };

    return () => es.close();
  }, [taskId]);

  const handleTransferStart = useCallback((newTaskId: string) => {
    setTaskId(newTaskId);
    setProgress(null);
    setIsTransferring(true);
  }, []);

  const handleCancel = useCallback(async () => {
    if (taskId) {
      await cancelTransfer(taskId);
      setIsTransferring(false);
    }
  }, [taskId]);

  const handleLogin = useCallback((token: string, email?: string) => {
    setAccessToken(token);
    setUserEmail(email ?? null);
  }, []);

  const handleLogout = useCallback(() => {
    setAccessToken(null);
    setUserEmail(null);
    setTaskId(null);
    setProgress(null);
    setIsTransferring(false);
  }, []);

  const handleDismiss = useCallback(() => {
    setProgress(null);
    setTaskId(null);
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
