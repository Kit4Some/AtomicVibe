import { Sun, Moon, TerminalSquare, Code2, Play } from "lucide-react";
import { useAppState, useAppDispatch } from "../context/AppContext";
import { startExecution } from "../api/execute";

interface MenuBarProps {
  theme: "light" | "dark";
  onToggleTheme: () => void;
}

const isElectron = !!window.electronAPI;
const WORKSPACE_CWD = "."; // Current working directory

export default function MenuBar({ theme, onToggleTheme }: MenuBarProps) {
  const { planId, jobId } = useAppState();
  const dispatch = useAppDispatch();

  const handleOpenTerminal = () => {
    if (isElectron) {
      window.electronAPI!.openTerminal(WORKSPACE_CWD);
    }
  };

  const handleOpenEditor = (editor: string) => {
    if (isElectron) {
      window.electronAPI!.openEditor(editor, WORKSPACE_CWD);
    }
  };

  const handleStart = async () => {
    if (!planId || jobId) return;
    const res = await startExecution(planId);
    dispatch({ type: "SET_JOB_ID", payload: res.job_id });
  };

  return (
    <div className="flex h-9 items-center justify-between border-b border-ds-border bg-ds-surface px-3">
      {/* Left */}
      <div className="flex items-center gap-1">
        {/* Theme toggle */}
        <button
          onClick={onToggleTheme}
          className="flex h-7 w-7 items-center justify-center rounded-[var(--radius-md)] text-ds-icon transition-colors hover:bg-ds-surface-hover hover:text-ds-text"
          title={theme === "dark" ? "Light mode" : "Dark mode"}
        >
          {theme === "dark" ? (
            <Sun size={15} strokeWidth={1.8} />
          ) : (
            <Moon size={15} strokeWidth={1.8} />
          )}
        </button>
      </div>

      {/* Right: action buttons */}
      <div className="flex items-center gap-1">
        {/* Terminal */}
        <button
          onClick={handleOpenTerminal}
          disabled={!isElectron}
          className="flex h-7 items-center gap-1.5 rounded-[var(--radius-md)] px-2 text-[12px] font-medium text-ds-text-secondary transition-colors hover:bg-ds-surface-hover hover:text-ds-text disabled:opacity-40"
          title="Open Terminal"
        >
          <TerminalSquare size={15} strokeWidth={1.8} />
          <span className="hidden sm:inline">Terminal</span>
        </button>

        {/* Code Editor */}
        <div className="relative group">
          <button
            onClick={() => handleOpenEditor("code")}
            disabled={!isElectron}
            className="flex h-7 items-center gap-1.5 rounded-[var(--radius-md)] px-2 text-[12px] font-medium text-ds-text-secondary transition-colors hover:bg-ds-surface-hover hover:text-ds-text disabled:opacity-40"
            title="Open in VSCode (right-click for AntiGravity)"
            onContextMenu={(e) => {
              e.preventDefault();
              handleOpenEditor("antigravity");
            }}
          >
            <Code2 size={15} strokeWidth={1.8} />
            <span className="hidden sm:inline">Editor</span>
          </button>
        </div>

        {/* Start / Play */}
        <button
          onClick={handleStart}
          disabled={!planId || !!jobId}
          className="flex h-7 items-center gap-1.5 rounded-[var(--radius-md)] bg-ds-success px-3 text-[12px] font-medium text-white transition-colors hover:brightness-110 disabled:opacity-40"
          title="Start Execution"
        >
          <Play size={14} strokeWidth={2} fill="currentColor" />
          <span className="hidden sm:inline">Start</span>
        </button>
      </div>
    </div>
  );
}
