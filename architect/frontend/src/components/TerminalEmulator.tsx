import { useEffect, useRef } from "react";
import { Terminal } from "@xterm/xterm";
import { FitAddon } from "@xterm/addon-fit";
import { useWebSocket } from "../hooks/useWebSocket";
import "@xterm/xterm/css/xterm.css";

interface TerminalEmulatorProps {
  wsUrl: string | null;
}

export default function TerminalEmulator({ wsUrl }: TerminalEmulatorProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const terminalRef = useRef<Terminal | null>(null);
  const fitAddonRef = useRef<FitAddon | null>(null);

  const { status, sendMessage } = useWebSocket(wsUrl, {
    onMessage: (data) => {
      terminalRef.current?.write(data);
    },
    reconnect: true,
  });

  useEffect(() => {
    if (!containerRef.current) return;

    const terminal = new Terminal({
      theme: {
        background: "#0a0a0f",
        foreground: "#ececf1",
        cursor: "#3b82f6",
        selectionBackground: "rgba(59, 130, 246, 0.3)",
      },
      fontSize: 14,
      fontFamily: "var(--font-mono)",
      cursorBlink: true,
    });

    const fitAddon = new FitAddon();
    terminal.loadAddon(fitAddon);
    terminal.open(containerRef.current);
    fitAddon.fit();

    terminal.onData((data) => {
      sendMessage(data);
    });

    terminalRef.current = terminal;
    fitAddonRef.current = fitAddon;

    const handleResize = () => fitAddon.fit();
    window.addEventListener("resize", handleResize);

    return () => {
      window.removeEventListener("resize", handleResize);
      terminal.dispose();
    };
  }, [sendMessage]);

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center gap-2 border-b border-ds-border bg-ds-surface px-3 py-1.5">
        <span
          className={`h-2 w-2 rounded-full ${
            status === "connected"
              ? "bg-ds-success"
              : status === "connecting"
                ? "bg-ds-warning"
                : "bg-ds-error"
          }`}
        />
        <span className="text-xs text-ds-text-secondary">
          {status === "connected"
            ? "Connected"
            : status === "connecting"
              ? "Connecting..."
              : "Disconnected"}
        </span>
      </div>
      <div ref={containerRef} className="flex-1" />
    </div>
  );
}
