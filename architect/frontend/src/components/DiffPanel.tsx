import { useEffect, useState, useCallback } from "react";
import DiffViewer from "./DiffViewer";
import { getDiff } from "../api/diff";
import { useAppState } from "../context/AppContext";
import { useWebSocket } from "../hooks/useWebSocket";
import type { DiffFile } from "../api/types";

const STATUS_COLORS: Record<string, string> = {
  added: "text-ds-success bg-ds-success-subtle",
  modified: "text-ds-warning bg-ds-warning-subtle",
  deleted: "text-ds-error bg-ds-error-subtle",
};

interface DiffPanelProps {
  selectedFilePath?: string | null;
  onSelectedFileChange?: (path: string | null) => void;
  onFilesChange?: (files: DiffFile[]) => void;
}

export default function DiffPanel({
  selectedFilePath,
  onSelectedFileChange,
  onFilesChange,
}: DiffPanelProps) {
  const { jobId } = useAppState();
  const [files, setFiles] = useState<DiffFile[]>([]);

  // Use external selection if provided, otherwise internal
  const [internalSelected, setInternalSelected] = useState<string | null>(null);
  const selected = selectedFilePath ?? internalSelected;
  const setSelected = useCallback((path: string | null) => {
    setInternalSelected(path);
    onSelectedFileChange?.(path);
  }, [onSelectedFileChange]);

  const fetchDiffs = useCallback(() => {
    if (!jobId) return;
    getDiff(jobId).then((res) => {
      setFiles(res.files);
      onFilesChange?.(res.files);
      if (res.files.length > 0 && !selected) {
        setSelected(res.files[0]!.path);
      }
    }).catch(() => {});
  }, [jobId, selected, onFilesChange, setSelected]);

  useEffect(() => {
    fetchDiffs();
  }, [fetchDiffs]);

  const wsUrl = jobId ? `/ws/progress/${jobId}` : null;

  const handleProgressMessage = useCallback((data: string) => {
    try {
      const parsed = JSON.parse(data);
      if (parsed.type === "heartbeat") return;
      fetchDiffs();
    } catch {
      // ignore
    }
  }, [fetchDiffs]);

  useWebSocket(wsUrl, { onMessage: handleProgressMessage, reconnect: false });

  const selectedFile = files.find((f) => f.path === selected);

  if (!jobId) {
    return (
      <div className="flex h-full items-center justify-center text-ds-text-tertiary text-[13px]">
        <div className="text-center">
          <p className="mb-1 text-lg font-medium text-ds-text-secondary">No active session</p>
          <p>Start a plan in the chat to see agent actions here</p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex h-full flex-col">
      {/* File tabs */}
      {files.length > 0 && (
        <div className="flex items-center gap-1 overflow-x-auto px-2 py-1.5">
          {files.map((file) => {
            const isActive = file.path === selected;
            return (
              <button
                key={file.path}
                onClick={() => setSelected(file.path)}
                className={`flex items-center gap-1.5 rounded-[var(--radius-md)] px-3 py-1 text-[12px] transition-colors ${
                  isActive
                    ? "bg-ds-surface text-ds-text"
                    : "text-ds-text-tertiary hover:bg-ds-surface-hover hover:text-ds-text-secondary"
                }`}
              >
                <span
                  className={`rounded-[var(--radius-sm)] px-1 py-px text-[9px] font-bold uppercase ${STATUS_COLORS[file.status] ?? ""}`}
                >
                  {file.status[0]}
                </span>
                <span className="max-w-[180px] truncate">{file.path.split("/").pop()}</span>
              </button>
            );
          })}
        </div>
      )}

      {/* Diff content */}
      <div className="flex-1 overflow-auto">
        {selectedFile ? (
          <DiffViewer
            oldValue={selectedFile.old_content}
            newValue={selectedFile.new_content}
            fileName={selectedFile.path}
          />
        ) : files.length === 0 ? (
          <div className="flex h-full items-center justify-center text-ds-text-tertiary text-[13px]">
            Waiting for agent actions...
          </div>
        ) : (
          <div className="flex h-full items-center justify-center text-ds-text-tertiary text-[13px]">
            Select a file tab to view diff
          </div>
        )}
      </div>
    </div>
  );
}
