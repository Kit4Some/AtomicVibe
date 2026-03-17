interface ProgressTrackerProps {
  phase: number;
  totalPhases: number;
  sprint: number;
  progress: number;
  status: string;
}

const PHASE_LABELS = ["Plan", "Generate", "Execute", "Deliver"];

export default function ProgressTracker({
  phase,
  totalPhases,
  sprint,
  progress,
  status,
}: ProgressTrackerProps) {
  const pct = Math.round(progress * 100);

  return (
    <div className="rounded-[var(--radius-xl)] border border-ds-border bg-ds-surface p-4">
      {/* Phase segments */}
      <div className="mb-3 flex gap-1">
        {Array.from({ length: totalPhases }, (_, i) => {
          const idx = i + 1;
          const label = PHASE_LABELS[i] ?? `Phase ${idx}`;
          const isActive = idx === phase;
          const isDone = idx < phase;
          return (
            <div
              key={idx}
              className={`flex-1 rounded-[var(--radius-md)] py-1 text-center text-xs font-medium transition-colors ${
                isDone
                  ? "bg-ds-success text-white"
                  : isActive
                    ? "bg-ds-accent text-ds-accent-text"
                    : "bg-ds-surface-hover text-ds-text-tertiary"
              }`}
            >
              {label}
            </div>
          );
        })}
      </div>

      {/* Progress bar */}
      <div className="mb-2 h-2 overflow-hidden rounded-full bg-ds-surface-hover">
        <div
          className="h-full rounded-full bg-gradient-to-r from-ds-accent to-cyan-400 transition-all duration-500"
          style={{ width: `${pct}%` }}
        />
      </div>

      {/* Info row */}
      <div className="flex items-center justify-between text-xs text-ds-text-secondary">
        <span>
          Phase {phase}/{totalPhases} &middot; Sprint {sprint}
        </span>
        <span className="font-mono">{pct}%</span>
        <span
          className={`rounded-[var(--radius-sm)] px-1.5 py-0.5 text-[10px] font-semibold uppercase ${
            status === "running"
              ? "bg-ds-accent-subtle text-ds-accent"
              : status === "completed"
                ? "bg-ds-success-subtle text-ds-success"
                : "bg-ds-surface-hover text-ds-text-tertiary"
          }`}
        >
          {status}
        </span>
      </div>
    </div>
  );
}
