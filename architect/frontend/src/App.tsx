import { useState, useEffect, useCallback, useRef } from "react";
import { PanelLeftOpen, Loader2 } from "lucide-react";
import { AppProvider, useAppState, useAppDispatch } from "./context/AppContext";
import { getSettings, setTier as setTierApi } from "./api/settings";
import TitleBar from "./components/TitleBar";
import SidePanel from "./components/SidePanel";
import DiffPanel from "./components/DiffPanel";
import ChatPanel from "./components/ChatPanel";
import ApiKeySetup from "./components/ApiKeySetup";
import type { ProgressMessage, DiffFile, Tier } from "./api/types";

function getInitialTheme(): "light" | "dark" {
  if (typeof window === "undefined") return "dark";
  const stored = localStorage.getItem("architect-theme");
  if (stored === "light" || stored === "dark") return stored;
  return "dark";
}

/* --- Resize constants --- */
const SIDE_MIN = 180;
const SIDE_DEFAULT = 240;
const CHAT_MIN = 280;
const CHAT_DEFAULT = 360;
const DIFF_MIN = 300;
const GAP = 1; // matches --gap-panel

function AppLayout() {
  const { apiKeyConfigured, tier } = useAppState();
  const dispatch = useAppDispatch();

  const [theme, setTheme] = useState<"light" | "dark">(getInitialTheme);
  const [logs, setLogs] = useState<ProgressMessage[]>([]);
  const [diffFiles, setDiffFiles] = useState<DiffFile[]>([]);
  const [selectedFile, setSelectedFile] = useState<string | null>(null);
  const [sidePanelExpanded, setSidePanelExpanded] = useState(true);

  // Plan mode state
  const [selectedVibeFile, setSelectedVibeFile] = useState<string | null>(null);

  // Coding mode state
  const [selectedAgent, setSelectedAgent] = useState<string | null>(null);

  // Fetch settings on mount
  useEffect(() => {
    getSettings()
      .then((s) => {
        dispatch({ type: "SET_API_KEY_CONFIGURED", payload: s.api_key_configured });
        dispatch({ type: "SET_TIER", payload: s.tier });
      })
      .catch(() => {
        dispatch({ type: "SET_API_KEY_CONFIGURED", payload: false });
      });
  }, [dispatch]);

  // Resizable panel widths
  const [sideWidth, setSideWidth] = useState(SIDE_DEFAULT);
  const [chatWidth, setChatWidth] = useState(CHAT_DEFAULT);
  const containerRef = useRef<HTMLDivElement>(null);
  const draggingRef = useRef<"side" | "chat" | null>(null);
  const startXRef = useRef(0);
  const startWidthRef = useRef(0);

  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
    localStorage.setItem("architect-theme", theme);
  }, [theme]);

  const toggleTheme = () =>
    setTheme((prev) => (prev === "dark" ? "light" : "dark"));

  const handleLogsChange = useCallback((l: ProgressMessage[]) => setLogs(l), []);
  const handleDiffFilesChange = useCallback((f: DiffFile[]) => setDiffFiles(f), []);

  const handleSelectFile = useCallback((path: string) => {
    setSelectedFile(path);
  }, []);

  const handleSelectVibeFile = useCallback((path: string) => {
    setSelectedVibeFile(path);
  }, []);

  const handleCreateVibeFile = useCallback(() => {
    setSelectedVibeFile("__new__");
  }, []);

  const handleSelectAgent = useCallback((agentId: string | null) => {
    setSelectedAgent(agentId);
  }, []);

  const handleTierChange = useCallback(
    async (newTier: Tier) => {
      try {
        const res = await setTierApi(newTier);
        dispatch({ type: "SET_TIER", payload: res.tier as Tier });
      } catch {
        // silently ignore
      }
    },
    [dispatch],
  );

  /* --- Drag resize logic --- */
  const handleMouseDown = useCallback(
    (handle: "side" | "chat", e: React.MouseEvent) => {
      e.preventDefault();
      draggingRef.current = handle;
      startXRef.current = e.clientX;
      startWidthRef.current = handle === "side" ? sideWidth : chatWidth;
      document.body.style.cursor = "col-resize";
      document.body.style.userSelect = "none";
    },
    [sideWidth, chatWidth],
  );

  useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
      if (!draggingRef.current || !containerRef.current) return;
      const containerWidth = containerRef.current.offsetWidth;
      const delta = e.clientX - startXRef.current;

      if (draggingRef.current === "side") {
        const sideExpanded = sidePanelExpanded;
        if (!sideExpanded) return;
        const newSide = Math.max(SIDE_MIN, startWidthRef.current + delta);
        // Ensure diff panel keeps minimum width
        const remainingForDiff = containerWidth - newSide - chatWidth - GAP * 3;
        if (remainingForDiff >= DIFF_MIN) {
          setSideWidth(newSide);
        } else {
          setSideWidth(containerWidth - chatWidth - DIFF_MIN - GAP * 3);
        }
      } else {
        const newChat = Math.max(CHAT_MIN, startWidthRef.current + delta);
        const sideW = sidePanelExpanded ? sideWidth : 0;
        const remainingForDiff = containerWidth - sideW - newChat - GAP * (sidePanelExpanded ? 3 : 2);
        if (remainingForDiff >= DIFF_MIN) {
          setChatWidth(newChat);
        } else {
          setChatWidth(containerWidth - sideW - DIFF_MIN - GAP * (sidePanelExpanded ? 3 : 2));
        }
      }
    };

    const handleMouseUp = () => {
      if (draggingRef.current) {
        draggingRef.current = null;
        document.body.style.cursor = "";
        document.body.style.userSelect = "";
      }
    };

    window.addEventListener("mousemove", handleMouseMove);
    window.addEventListener("mouseup", handleMouseUp);
    return () => {
      window.removeEventListener("mousemove", handleMouseMove);
      window.removeEventListener("mouseup", handleMouseUp);
    };
  }, [sideWidth, chatWidth, sidePanelExpanded]);

  // Loading state
  if (apiKeyConfigured === null) {
    return (
      <div className="flex h-screen items-center justify-center bg-ds-bg-subtle">
        <Loader2 size={24} className="animate-spin text-ds-text-tertiary" />
      </div>
    );
  }

  // API key not configured — show setup screen
  if (apiKeyConfigured === false) {
    return <ApiKeySetup />;
  }

  return (
    <div className="flex h-screen flex-col bg-ds-bg-subtle text-ds-text">
      {/* Title bar */}
      <TitleBar theme={theme} onToggleTheme={toggleTheme} tier={tier} onTierChange={handleTierChange} />

      {/* Main content */}
      <div
        ref={containerRef}
        className="relative flex min-h-0 flex-1 overflow-hidden p-[var(--gap-panel)] pt-0"
        style={{ gap: `${GAP}px` }}
      >
        {/* Floating expand button */}
        {!sidePanelExpanded && (
          <button
            onClick={() => setSidePanelExpanded(true)}
            className="absolute left-3 top-3 z-10 flex h-7 w-7 items-center justify-center rounded-full bg-ds-surface text-ds-icon shadow-sm transition-colors hover:bg-ds-surface-hover hover:text-ds-text"
            title="Open side panel"
          >
            <PanelLeftOpen size={13} strokeWidth={1.8} />
          </button>
        )}

        {/* Side Panel */}
        {sidePanelExpanded && (
          <div style={{ width: sideWidth, flexShrink: 0 }}>
            <SidePanel
              files={diffFiles}
              logs={logs}
              onSelectFile={handleSelectFile}
              selectedFile={selectedFile}
              expanded={sidePanelExpanded}
              onCollapse={() => setSidePanelExpanded(false)}
              selectedVibeFile={selectedVibeFile}
              onSelectVibeFile={handleSelectVibeFile}
              onCreateVibeFile={handleCreateVibeFile}
              selectedAgent={selectedAgent}
              onSelectAgent={handleSelectAgent}
            />
          </div>
        )}

        {/* Resize handle: Side ↔ Chat */}
        {sidePanelExpanded && (
          <div
            onMouseDown={(e) => handleMouseDown("side", e)}
            className="group flex w-0 cursor-col-resize items-center justify-center"
            style={{ marginLeft: -GAP / 2, marginRight: -GAP / 2, width: GAP, zIndex: 5 }}
          >
            <div className="h-8 w-1 rounded-full bg-transparent transition-colors group-hover:bg-ds-border group-active:bg-ds-accent" />
          </div>
        )}

        {/* Chat Panel */}
        <div
          className="flex-shrink-0 overflow-hidden rounded-[var(--radius-panel)] bg-ds-bg"
          style={{ width: chatWidth }}
        >
          <ChatPanel
            onLogsChange={handleLogsChange}
            selectedVibeFile={selectedVibeFile}
            onVibeFileSelected={setSelectedVibeFile}
            selectedAgent={selectedAgent}
            onAgentDeselected={() => setSelectedAgent(null)}
          />
        </div>

        {/* Resize handle: Chat ↔ Diff */}
        <div
          onMouseDown={(e) => handleMouseDown("chat", e)}
          className="group flex w-0 cursor-col-resize items-center justify-center"
          style={{ marginLeft: -GAP / 2, marginRight: -GAP / 2, width: GAP, zIndex: 5 }}
        >
          <div className="h-8 w-1 rounded-full bg-transparent transition-colors group-hover:bg-ds-border group-active:bg-ds-accent" />
        </div>

        {/* Diff Panel */}
        <div className="min-w-0 flex-1 overflow-hidden rounded-[var(--radius-panel)] bg-ds-bg">
          <DiffPanel
            selectedFilePath={selectedFile}
            onSelectedFileChange={setSelectedFile}
            onFilesChange={handleDiffFilesChange}
          />
        </div>
      </div>
    </div>
  );
}

export default function App() {
  return (
    <AppProvider>
      <AppLayout />
    </AppProvider>
  );
}
