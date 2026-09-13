"use client";

import { useState, useRef } from "react";
import { Link2, FolderOpen, FileText, Send, X } from "lucide-react";
import { startTransfer } from "@/lib/api";

interface DownloadFormProps {
  accessToken: string;
  isTransferring: boolean;
  onTransferStart: (taskId: string) => void;
  onCancel: () => void;
}

export default function DownloadForm({
  accessToken,
  isTransferring,
  onTransferStart,
  onCancel,
}: DownloadFormProps) {
  const [url, setUrl] = useState("");
  const [folderName, setFolderName] = useState("Downloads/movie colab");
  const [filename, setFilename] = useState("");
  const [error, setError] = useState<string | null>(null);
  const urlRef = useRef<HTMLInputElement>(null);

  /** Try to infer a filename from the URL path on paste. */
  const handlePaste = (e: React.ClipboardEvent<HTMLInputElement>) => {
    const pasted = e.clipboardData.getData("text");
    if (!filename) {
      try {
        const u = new URL(pasted);
        const segs = u.pathname.split("/").filter(Boolean);
        const last = segs[segs.length - 1] ?? "";
        if (last && last.includes(".")) setFilename(decodeURIComponent(last));
      } catch {
        /* not a URL */
      }
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    const trimmedUrl = url.trim();
    if (!trimmedUrl) {
      setError("Please enter a source URL.");
      urlRef.current?.focus();
      return;
    }
    try {
      new URL(trimmedUrl);
    } catch {
      setError("Please enter a valid URL (must start with http:// or https://).");
      return;
    }

    try {
      const { task_id } = await startTransfer({
        url: trimmedUrl,
        access_token: accessToken,
        folder_name: folderName.trim() || "Downloads/movie colab",
        filename: filename.trim() || undefined,
      });
      onTransferStart(task_id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to start transfer.");
    }
  };

  const inputCls =
    "w-full bg-slate-900/60 border border-slate-600 focus:border-blue-500 " +
    "focus:ring-1 focus:ring-blue-500 rounded-lg pl-10 pr-4 py-3 text-white " +
    "placeholder-slate-500 text-sm outline-none transition-colors disabled:opacity-50";

  return (
    <form
      onSubmit={handleSubmit}
      className="bg-slate-800/60 backdrop-blur border border-slate-700 rounded-2xl p-6 space-y-4"
    >
      <h2 className="text-white font-semibold text-lg flex items-center gap-2">
        <Send className="w-5 h-5 text-blue-400" />
        Start Transfer
      </h2>

      {/* Source URL */}
      <div className="space-y-1">
        <label className="block text-sm text-slate-400">Source URL</label>
        <div className="relative">
          <Link2 className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500 pointer-events-none" />
          <input
            ref={urlRef}
            type="text"
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            onPaste={handlePaste}
            placeholder="https://example.com/file.mp4  or  YouTube URL"
            disabled={isTransferring}
            className={inputCls}
          />
        </div>
      </div>

      {/* Drive folder path */}
      <div className="space-y-1">
        <label className="block text-sm text-slate-400">Drive Folder Path</label>
        <div className="relative">
          <FolderOpen className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500 pointer-events-none" />
          <input
            type="text"
            value={folderName}
            onChange={(e) => setFolderName(e.target.value)}
            placeholder="Downloads/movie colab"
            disabled={isTransferring}
            className={inputCls}
          />
        </div>
      </div>

      {/* Filename override */}
      <div className="space-y-1">
        <label className="block text-sm text-slate-400">
          Filename Override{" "}
          <span className="text-slate-600 text-xs">(optional)</span>
        </label>
        <div className="relative">
          <FileText className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500 pointer-events-none" />
          <input
            type="text"
            value={filename}
            onChange={(e) => setFilename(e.target.value)}
            placeholder="auto-detected from URL headers"
            disabled={isTransferring}
            className={inputCls}
          />
        </div>
      </div>

      {/* Error */}
      {error && (
        <p className="text-red-400 text-sm bg-red-950/30 border border-red-800/50 rounded-lg px-4 py-2">
          {error}
        </p>
      )}

      {/* Action buttons */}
      <div className="flex gap-3 pt-1">
        <button
          type="submit"
          disabled={isTransferring || !url.trim()}
          className="flex-1 flex items-center justify-center gap-2 bg-blue-600 hover:bg-blue-500 disabled:bg-slate-700 disabled:text-slate-500 text-white font-semibold py-3 rounded-xl transition-colors"
        >
          <Send className="w-4 h-4" />
          {isTransferring ? "Transferring…" : "Send to Drive"}
        </button>

        {isTransferring && (
          <button
            type="button"
            onClick={onCancel}
            className="flex items-center gap-2 bg-red-900/40 hover:bg-red-800/60 border border-red-700/50 text-red-300 font-medium px-4 py-3 rounded-xl transition-colors"
          >
            <X className="w-4 h-4" />
            Cancel
          </button>
        )}
      </div>
    </form>
  );
}
