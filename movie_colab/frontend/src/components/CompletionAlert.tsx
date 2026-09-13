"use client";

import { useEffect } from "react";
import { CheckCircle2, XCircle, ExternalLink, X } from "lucide-react";
import type { ProgressEvent } from "@/lib/api";

/**
 * Play a short synthetic success ping using the Web Audio API.
 * Falls back silently if AudioContext is not available.
 */
function playSuccessPing(): void {
  try {
    const ctx = new AudioContext();
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.connect(gain);
    gain.connect(ctx.destination);
    osc.type = "sine";
    osc.frequency.setValueAtTime(880, ctx.currentTime);
    osc.frequency.exponentialRampToValueAtTime(440, ctx.currentTime + 0.45);
    gain.gain.setValueAtTime(0.25, ctx.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.45);
    osc.start();
    osc.stop(ctx.currentTime + 0.45);
  } catch {
    /* AudioContext unavailable — safe to ignore */
  }
}

interface CompletionAlertProps {
  progress: ProgressEvent;
  onDismiss: () => void;
}

export default function CompletionAlert({
  progress,
  onDismiss,
}: CompletionAlertProps) {
  const isSuccess = progress.status === "completed";

  useEffect(() => {
    if (isSuccess) playSuccessPing();
  }, [isSuccess]);

  return (
    <div
      className={`relative rounded-2xl border p-6 space-y-3 transition-all ${
        isSuccess
          ? "bg-green-950/40 border-green-700/50"
          : "bg-red-950/40 border-red-700/50"
      }`}
    >
      {/* Dismiss */}
      <button
        onClick={onDismiss}
        className="absolute top-4 right-4 text-slate-500 hover:text-slate-300 transition-colors"
        aria-label="Dismiss"
      >
        <X className="w-4 h-4" />
      </button>

      {/* Status icon + title */}
      <div className="flex items-center gap-3">
        {isSuccess ? (
          <CheckCircle2 className="w-9 h-9 text-green-400 flex-shrink-0" />
        ) : (
          <XCircle className="w-9 h-9 text-red-400 flex-shrink-0" />
        )}
        <div>
          <p
            className={`font-semibold text-lg leading-tight ${
              isSuccess ? "text-green-300" : "text-red-300"
            }`}
          >
            {isSuccess ? "File saved to Google Drive!" : "Transfer failed"}
          </p>
          {progress.error && (
            <p className="text-sm text-red-400 mt-0.5">{progress.error}</p>
          )}
        </div>
      </div>

      {/* Drive link on success */}
      {isSuccess && progress.drive_file_link && (
        <a
          href={progress.drive_file_link}
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex items-center gap-2 bg-green-800/50 hover:bg-green-700/60 text-green-200 text-sm font-medium px-4 py-2 rounded-lg transition-colors"
        >
          <ExternalLink className="w-4 h-4" />
          Open in Google Drive
        </a>
      )}

      {/* File ID (for developers) */}
      {isSuccess && progress.drive_file_id && (
        <p className="text-xs text-slate-500 font-mono truncate">
          ID: {progress.drive_file_id}
        </p>
      )}
    </div>
  );
}
