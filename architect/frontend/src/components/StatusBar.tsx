import { useAppState } from "../context/AppContext";

interface StatusBarProps {
  phase: number;
  totalPhases: number;
  sprint: number;
  fileCount: number;
  cost: number;
  errorCount: number;
  isRunning: boolean;
}

export default function StatusBar({
  phase,
  totalPhases,
  sprint,
  fileCount,
  cost,
  errorCount,
  isRunning,
}: StatusBarProps) {
  const { planId, jobId } = useAppState();

  return (
    <div className="flex h-6 items-center justify-between border-t border-ds-border bg-ds-bg-subtle px-3 text-[11px] text-ds-text-tertiary">
      {/* Left */}
      <div className="flex items-center gap-3">
        <span className="flex items-center gap-1.5">
          <span
            className={`h-1.5 w-1.5 rounded-full ${
              isRunning
                ? "bg-ds-success animate-pulse"
                : jobId
                  ? "bg-ds-accent"
                  : "bg-ds-text-tertiary"
            }`}
          />
          {isRunning ? "Running" : jobId ? "Idle" : "Ready"}
        </span>
        {jobId && (
          <>
            <span>Phase {phase}/{totalPhases}</span>
            <span>Sprint {sprint}</span>
          </>
        )}
      </div>

      {/* Right */}
      <div className="flex items-center gap-3">
        {jobId && (
          <>
            <span>{fileCount} files</span>
            <span>${cost.toFixed(2)}</span>
            {errorCount > 0 && (
              <span className="text-ds-error">{errorCount} errors</span>
            )}
          </>
        )}
        {planId && !jobId && <span>Planning...</span>}
      </div>
    </div>
  );
}
