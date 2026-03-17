import { useState, useRef, useEffect } from "react";
import { Minus, Square, X, Sun, Moon, TerminalSquare, Code2, Play, ChevronDown, Zap } from "lucide-react";
import { useAppState, useAppDispatch } from "../context/AppContext";
import { startExecution } from "../api/execute";
import type { Tier } from "../api/types";

interface TitleBarProps {
  theme: "light" | "dark";
  onToggleTheme: () => void;
  tier?: Tier;
  onTierChange?: (tier: Tier) => void;
}

const isElectron = !!window.electronAPI;
const WORKSPACE_CWD = ".";

const TIER_INFO: { value: Tier; label: string; desc: string }[] = [
  { value: "low", label: "Low", desc: "Haiku only" },
  { value: "mid", label: "Mid", desc: "Sonnet + Haiku" },
  { value: "high", label: "High", desc: "Opus + Sonnet + Haiku" },
  { value: "max", label: "Max", desc: "Opus + Sonnet" },
];

export default function TitleBar({ theme, onToggleTheme, tier = "mid", onTierChange }: TitleBarProps) {
  const { planId, jobId } = useAppState();
  const dispatch = useAppDispatch();
  const [openMenuOpen, setOpenMenuOpen] = useState(false);
  const [tierMenuOpen, setTierMenuOpen] = useState(false);
  const openMenuRef = useRef<HTMLDivElement>(null);
  const tierMenuRef = useRef<HTMLDivElement>(null);

  // Close dropdowns on outside click
  useEffect(() => {
    if (!openMenuOpen && !tierMenuOpen) return;
    const handleClick = (e: MouseEvent) => {
      if (openMenuOpen && openMenuRef.current && !openMenuRef.current.contains(e.target as Node)) {
        setOpenMenuOpen(false);
      }
      if (tierMenuOpen && tierMenuRef.current && !tierMenuRef.current.contains(e.target as Node)) {
        setTierMenuOpen(false);
      }
    };
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, [openMenuOpen, tierMenuOpen]);

  const handleOpenTerminal = () => {
    if (isElectron) {
      window.electronAPI!.openTerminal(WORKSPACE_CWD);
    }
    setOpenMenuOpen(false);
  };

  const handleOpenEditor = (editor: string) => {
    if (isElectron) {
      window.electronAPI!.openEditor(editor, WORKSPACE_CWD);
    }
    setOpenMenuOpen(false);
  };

  const handleStart = async () => {
    if (!planId || jobId) return;
    const res = await startExecution(planId);
    dispatch({ type: "SET_JOB_ID", payload: res.job_id });
  };

  const handleTierSelect = (t: Tier) => {
    onTierChange?.(t);
    setTierMenuOpen(false);
  };

  const currentTierInfo = TIER_INFO.find((t) => t.value === tier) ?? TIER_INFO[1];

  return (
    <div className="title-bar flex h-8 items-center bg-ds-bg-subtle select-none">
      {/* Left: Theme toggle */}
      <div className="title-bar-controls flex items-center pl-2">
        <button
          onClick={onToggleTheme}
          className="flex h-6 w-6 items-center justify-center rounded-[var(--radius-md)] text-ds-icon transition-colors hover:bg-ds-surface-hover hover:text-ds-text"
          title={theme === "dark" ? "Light mode" : "Dark mode"}
        >
          {theme === "dark" ? (
            <Sun size={13} strokeWidth={1.8} />
          ) : (
            <Moon size={13} strokeWidth={1.8} />
          )}
        </button>
      </div>

      {/* Draggable spacer */}
      <div className="flex-1" />

      {/* Center: action buttons */}
      <div className="title-bar-controls flex items-center gap-1">
        {/* Tier selector dropdown */}
        <div ref={tierMenuRef} className="relative">
          <button
            onClick={() => setTierMenuOpen((v) => !v)}
            className="flex h-6 items-center gap-0.5 rounded-[var(--radius-md)] px-1.5 text-[11px] font-medium text-ds-text-secondary transition-colors hover:bg-ds-surface-hover hover:text-ds-text"
            title="Quality tier"
          >
            <Zap size={11} strokeWidth={2} />
            {currentTierInfo.label}
            <ChevronDown size={11} strokeWidth={2} className={`transition-transform ${tierMenuOpen ? "rotate-180" : ""}`} />
          </button>
          {tierMenuOpen && (
            <div className="title-bar-dropdown absolute left-0 top-full z-50 mt-1 min-w-[160px] rounded-[var(--radius-lg)] border border-ds-border bg-ds-surface py-1.5 shadow-lg">
              {TIER_INFO.map((t) => (
                <button
                  key={t.value}
                  onClick={() => handleTierSelect(t.value)}
                  className={`mx-1 flex w-[calc(100%-0.5rem)] items-center justify-between rounded-[var(--radius-md)] px-2 py-1.5 text-[11px] transition-colors hover:bg-ds-surface-hover ${
                    tier === t.value ? "text-ds-accent" : "text-ds-text-secondary hover:text-ds-text"
                  }`}
                >
                  <span className="font-medium">{t.label}</span>
                  <span className="text-[10px] text-ds-text-tertiary">{t.desc}</span>
                </button>
              ))}
            </div>
          )}
        </div>

        {/* Open accordion dropdown */}
        <div ref={openMenuRef} className="relative">
          <button
            onClick={() => setOpenMenuOpen((v) => !v)}
            className="flex h-6 items-center gap-0.5 rounded-[var(--radius-md)] px-1.5 text-[11px] font-medium text-ds-text-secondary transition-colors hover:bg-ds-surface-hover hover:text-ds-text"
            title="Open in external app"
          >
            Open
            <ChevronDown size={11} strokeWidth={2} className={`transition-transform ${openMenuOpen ? "rotate-180" : ""}`} />
          </button>
          {openMenuOpen && (
            <div className="title-bar-dropdown absolute left-0 top-full z-50 mt-1 min-w-[140px] rounded-[var(--radius-lg)] border border-ds-border bg-ds-surface py-1.5 shadow-lg">
              <button
                onClick={handleOpenTerminal}
                className="mx-1 flex w-[calc(100%-0.5rem)] items-center gap-2 rounded-[var(--radius-md)] px-2 py-1.5 text-[11px] text-ds-text-secondary transition-colors hover:bg-ds-surface-hover hover:text-ds-text"
                title="Open Terminal"
              >
                <TerminalSquare size={13} strokeWidth={1.8} />
                Terminal
              </button>
              <button
                onClick={() => handleOpenEditor("code")}
                className="mx-1 flex w-[calc(100%-0.5rem)] items-center gap-2 rounded-[var(--radius-md)] px-2 py-1.5 text-[11px] text-ds-text-secondary transition-colors hover:bg-ds-surface-hover hover:text-ds-text"
                title="Open in VSCode"
              >
                <Code2 size={13} strokeWidth={1.8} />
                VSCode
              </button>
              <button
                onClick={() => handleOpenEditor("antigravity")}
                className="mx-1 flex w-[calc(100%-0.5rem)] items-center gap-2 rounded-[var(--radius-md)] px-2 py-1.5 text-[11px] text-ds-text-secondary transition-colors hover:bg-ds-surface-hover hover:text-ds-text"
                title="Open in AntiGravity"
              >
                <Code2 size={13} strokeWidth={1.8} />
                AntiGravity
              </button>
            </div>
          )}
        </div>

        {/* Start / Play */}
        <button
          onClick={handleStart}
          disabled={!planId || !!jobId}
          className="flex h-6 items-center gap-1 rounded-[var(--radius-md)] bg-ds-success px-2 text-[11px] font-medium text-white transition-colors hover:brightness-110 disabled:opacity-40"
          title="Start Execution"
        >
          <Play size={12} strokeWidth={2} fill="currentColor" />
          <span className="hidden sm:inline">Start</span>
        </button>
      </div>

      {/* Draggable spacer */}
      <div className="flex-1" />

      {/* Window controls */}
      <div className="title-bar-controls flex items-center gap-0.5 pr-1">
        <button
          onClick={() => window.electronAPI?.minimizeWindow()}
          className="flex h-6 w-6 items-center justify-center rounded-full text-ds-icon transition-colors hover:bg-ds-surface-hover"
          title="Minimize"
        >
          <Minus size={13} strokeWidth={1.5} />
        </button>
        <button
          onClick={() => window.electronAPI?.maximizeWindow()}
          className="flex h-6 w-6 items-center justify-center rounded-full text-ds-icon transition-colors hover:bg-ds-surface-hover"
          title="Maximize"
        >
          <Square size={11} strokeWidth={1.5} />
        </button>
        <button
          onClick={() => window.electronAPI?.closeWindow()}
          className="flex h-6 w-6 items-center justify-center rounded-full text-ds-icon transition-colors hover:bg-ds-error hover:text-white"
          title="Close"
        >
          <X size={13} strokeWidth={1.5} />
        </button>
      </div>
    </div>
  );
}
