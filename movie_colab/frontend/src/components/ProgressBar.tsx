"use client";

import {
  RefreshCw,
  Download,
  Cloud,
  HardDrive,
  CheckCircle,
  XCircle,
} from "lucide-react";
import type { ProgressEvent } from "@/lib/api";

const STATUS_LABELS: Record<string, string> = {
  queued: "Queued",
  downloading: "Downloading from source",
  uploading_to_drive: "Uploading to Google Drive",
  syncing: "Syncing caches (os.sync)",
  completed: "Transfer complete",
  failed: "Transfer failed",
};

const STATUS_ICONS: Record<string, React.ReactNode> = {
  queued: <RefreshCw className="w-4 h-4 animate-spin text-slate-400" />,
  downloading: <Download className="w-4 h-4 animate-bounce text-blue-400" />,
  uploading_to_drive: <Cloud className="w-4 h-4 animate-pulse text-cyan-400" />,
  syncing: <HardDrive className="w-4 h-4 animate-spin text-yellow-400" />,
  completed: <CheckCircle className="w-4 h-4 text-green-400" />,
  failed: <XCircle className="w-4 h-4 text-red-400" />,
};

function formatBytes(bytes: number): string {
  if (bytes === 0) return "0 B";
  const k = 1024;
  const sizes = ["B", "KB", "MB", "GB", "TB"];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return `${parseFloat((bytes / Math.pow(k, i)).toFixed(1))} ${sizes[i]}`;
}

interface ProgressBarProps {
  progress: ProgressEvent;
}

export default function ProgressBar({ progress }: ProgressBarProps) {
  const { status, percent, bytes_uploaded, bytes_downloaded, total_bytes, message } =
    progress;
  const pct = Math.min(100, Math.max(0, percent));
  const isError = status === "failed";
  const isSuccess = status === "completed";

  return (
    <div className="bg-slate-800/60 backdrop-blur border border-slate-700 rounded-2xl p-6 space-y-4">
      {/* Status row */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2 text-slate-300">
          {STATUS_ICONS[status] ?? (
            <RefreshCw className="w-4 h-4 animate-spin" />
          )}
          <span className="text-sm font-medium">
            {STATUS_LABELS[status] ?? status}
          </span>
        </div>
        <span
          className={`text-2xl font-bold tabular-nums ${
            isSuccess
              ? "text-green-400"
              : isError
              ? "text-red-400"
              : "text-white"
          }`}
        >
          {pct.toFixed(1)}%
        </span>
      </div>

      {/* Progress track */}
      <div className="relative h-3 bg-slate-700 rounded-full overflow-hidden">
        <div
          className={`h-full rounded-full transition-all duration-500 ease-out ${
            isSuccess
              ? "bg-green-500"
              : isError
              ? "bg-red-500"
              : "bg-gradient-to-r from-blue-500 to-cyan-400"
          }`}
          style={{ width: `${pct}%` }}
        />
        {/* Shimmer on active upload */}
        {!isSuccess && !isError && pct > 0 && pct < 100 && (
          <div className="absolute inset-0 overflow-hidden rounded-full pointer-events-none">
            <div className="absolute inset-y-0 w-1/3 bg-gradient-to-r from-transparent via-white/20 to-transparent animate-[progress-shine_1.5s_ease-in-out_infinite]" />
          </div>
        )}
      </div>

      {/* Byte stats */}
      <div className="flex items-center justify-between text-xs text-slate-400">
        <span>↓ {formatBytes(bytes_downloaded)} downloaded</span>
        {total_bytes > 0 && (
          <span className="text-slate-500">of {formatBytes(total_bytes)}</span>
        )}
        <span>↑ {formatBytes(bytes_uploaded)} → Drive</span>
      </div>

      {message && (
        <p className="text-xs text-slate-500 text-center truncate">{message}</p>
      )}
    </div>
  );
}
