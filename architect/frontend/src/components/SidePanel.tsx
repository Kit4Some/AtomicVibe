import { useState, useEffect, useCallback } from "react";
import {
  PanelLeftClose,
  FileText,
  Bot,
  Circle,
  CheckCircle2,
  AlertCircle,
  Loader2,
  Plus,
  Hand,
  MessageSquare,
} from "lucide-react";
import { useAppState } from "../context/AppContext";
import { listVibeFiles } from "../api/vibe";
import { listAgents } from "../api/agents";
import type { VibeFile, AgentDetail, ProgressMessage } from "../api/types";

type Mode = "plan" | "coding";

interface SidePanelProps {
  files: DiffFile[];
  logs: ProgressMessage[];
  onSelectFile?: (path: string) => void;
  selectedFile?: string | null;
  expanded: boolean;
  onCollapse: () => void;
  // Plan mode
  selectedVibeFile?: string | null;
  onSelectVibeFile?: (path: string) => void;
  onCreateVibeFile?: () => void;
  // Coding mode
  selectedAgent?: string | null;
  onSelectAgent?: (agentId: string | null) => void;
}

export default function SidePanel({
  files,
  logs,
  onSelectFile,
  selectedFile,
  expanded,
  onCollapse,
  selectedVibeFile,
  onSelectVibeFile,
  onCreateVibeFile,
  selectedAgent,
  onSelectAgent,
}: SidePanelProps) {
  const { planId, jobId } = useAppState();
  const [mode, setMode] = useState<Mode>(jobId ? "coding" : "plan");

  if (!expanded) {
    return null;
  }

  return (
    <div className="flex h-full w-full flex-col overflow-hidden rounded-[var(--radius-panel)] bg-ds-bg">
      {/* Header with collapse button */}
      <div className="flex items-center justify-between border-b border-ds-border-subtle px-2 py-1.5">
        <div className="flex items-center gap-1">
          <button
            onClick={() => setMode("plan")}
            className={`rounded-[var(--radius-md)] px-2.5 py-1 text-[11px] font-medium transition-colors ${
              mode === "plan"
                ? "bg-ds-accent-subtle text-ds-accent"
                : "text-ds-text-tertiary hover:text-ds-text-secondary"
            }`}
          >
            Plan
          </button>
          <button
            onClick={() => setMode("coding")}
            className={`rounded-[var(--radius-md)] px-2.5 py-1 text-[11px] font-medium transition-colors ${
              mode === "coding"
                ? "bg-ds-accent-subtle text-ds-accent"
                : "text-ds-text-tertiary hover:text-ds-text-secondary"
            }`}
          >
            Coding
          </button>
        </div>
        <button
          onClick={onCollapse}
          className="flex h-6 w-6 items-center justify-center rounded-[var(--radius-sm)] text-ds-icon transition-colors hover:bg-ds-surface-hover hover:text-ds-text"
          title="Collapse panel"
        >
          <PanelLeftClose size={14} strokeWidth={1.8} />
        </button>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto">
        {mode === "coding" ? (
          <CodingView
            logs={logs}
            selectedAgent={selectedAgent}
            onSelectAgent={onSelectAgent}
          />
        ) : (
          <PlanView
            planId={planId}
            selectedVibeFile={selectedVibeFile}
            onSelectVibeFile={onSelectVibeFile}
            onCreateVibeFile={onCreateVibeFile}
          />
        )}
      </div>
    </div>
  );
}

/* --- Plan Mode View --- */

function PlanView({
  planId,
  selectedVibeFile,
  onSelectVibeFile,
  onCreateVibeFile,
}: {
  planId: string | null;
  selectedVibeFile?: string | null;
  onSelectVibeFile?: (path: string) => void;
  onCreateVibeFile?: () => void;
}) {
  const [vibeFiles, setVibeFiles] = useState<VibeFile[]>([]);
  const [loading, setLoading] = useState(false);

  const fetchFiles = useCallback(() => {
    if (!planId) return;
    setLoading(true);
    listVibeFiles(planId)
      .then(setVibeFiles)
      .catch(() => setVibeFiles([]))
      .finally(() => setLoading(false));
  }, [planId]);

  useEffect(() => {
    fetchFiles();
  }, [fetchFiles]);

  if (!planId) {
    return (
      <div className="px-3 py-3 text-[11px] text-ds-text-tertiary">
        <p>No active plan.</p>
        <p className="mt-1">
          Describe your project in the chat to start planning.
        </p>
      </div>
    );
  }

  return (
    <div>
      {/* Header */}
      <div className="flex items-center justify-between px-3 py-2">
        <div className="flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-wider text-ds-text-tertiary">
          <FileText size={12} />
          Documents
          {vibeFiles.length > 0 && (
            <span className="ml-1 font-normal">{vibeFiles.length}</span>
          )}
        </div>
        <button
          onClick={onCreateVibeFile}
          className="flex h-5 w-5 items-center justify-center rounded-[var(--radius-sm)] text-ds-icon transition-colors hover:bg-ds-surface-hover hover:text-ds-text"
          title="New document"
        >
          <Plus size={12} strokeWidth={2} />
        </button>
      </div>

      {/* File list */}
      {loading ? (
        <div className="flex items-center gap-1.5 px-3 pb-2 text-[11px] text-ds-text-tertiary">
          <Loader2 size={11} className="animate-spin" />
          Loading...
        </div>
      ) : vibeFiles.length === 0 ? (
        <div className="px-3 pb-2 text-[11px] text-ds-text-tertiary">
          <p>No documents yet.</p>
          <p className="mt-1">
            Use the chat to create and edit plan documents.
          </p>
        </div>
      ) : (
        <div className="pb-1">
          {vibeFiles.map((file) => (
            <button
              key={file.path}
              onClick={() => onSelectVibeFile?.(file.path)}
              className={`flex w-full items-center gap-2 px-3 py-1.5 text-left transition-colors hover:bg-ds-surface-hover ${
                selectedVibeFile === file.path ? "bg-ds-accent-subtle" : ""
              }`}
            >
              <FileText
                size={12}
                strokeWidth={1.8}
                className={
                  selectedVibeFile === file.path
                    ? "text-ds-accent"
                    : "text-ds-icon"
                }
              />
              <span className="min-w-0 truncate text-[11px] text-ds-text-secondary">
                {file.name}
              </span>
            </button>
          ))}
        </div>
      )}

      {/* Help text */}
      <div className="border-t border-ds-border-subtle px-3 py-2">
        <p className="text-[10px] leading-relaxed text-ds-text-tertiary">
          Select a document to view it. Use the chat to edit, add, or refine
          your plan documents.
        </p>
      </div>
    </div>
  );
}

/* --- Coding Mode View --- */

const STATUS_COLORS: Record<string, string> = {
  added: "text-ds-success",
  modified: "text-ds-warning",
  deleted: "text-ds-error",
};

function CodingView({
  logs,
  selectedAgent,
  onSelectAgent,
}: {
  logs: ProgressMessage[];
  selectedAgent?: string | null;
  onSelectAgent?: (agentId: string | null) => void;
}) {
  const { jobId } = useAppState();
  const [agents, setAgents] = useState<AgentDetail[]>([]);

  // Fetch agents from API, fallback to deriving from logs
  const fetchAgents = useCallback(() => {
    if (!jobId) return;
    listAgents(jobId)
      .then(setAgents)
      .catch(() => {
        setAgents(deriveAgentsFromLogs(logs));
      });
  }, [jobId, logs]);

  useEffect(() => {
    fetchAgents();
  }, [fetchAgents]);

  useEffect(() => {
    if (jobId) fetchAgents();
  }, [logs.length, jobId, fetchAgents]);

  const runningCount = agents.filter(
    (a) => a.status === "running" || a.status === "waiting_for_human"
  ).length;

  return (
    <div>
      <div className="flex items-center gap-1.5 px-3 py-2 text-[10px] font-semibold uppercase tracking-wider text-ds-text-tertiary">
        <Bot size={12} />
        Agents
        {runningCount > 0 && (
          <span className="ml-auto rounded-full bg-ds-success-subtle px-1.5 py-px text-[9px] font-bold text-ds-success">
            {runningCount}
          </span>
        )}
      </div>
      {agents.length > 0 && (
        <div className="pb-1">
          {agents.map((agent) => (
            <button
              key={agent.agent_id}
              onClick={() =>
                onSelectAgent?.(
                  selectedAgent === agent.agent_id ? null : agent.agent_id
                )
              }
              className={`flex w-full items-start gap-2 px-3 py-1.5 text-left transition-colors hover:bg-ds-surface-hover ${
                selectedAgent === agent.agent_id ? "bg-ds-accent-subtle" : ""
              }`}
            >
              <span className="mt-0.5 flex-shrink-0">
                <AgentStatusIcon status={agent.status} />
              </span>
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-1">
                  <span className="truncate text-[11px] font-medium text-ds-text-secondary">
                    {agent.name}
                  </span>
                  {agent.status === "waiting_for_human" && (
                    <Hand
                      size={10}
                      className="flex-shrink-0 text-ds-warning"
                    />
                  )}
                  {agent.messages.length > 0 && (
                    <MessageSquare
                      size={10}
                      className="flex-shrink-0 text-ds-text-tertiary"
                    />
                  )}
                </div>
                <div className="truncate text-[10px] text-ds-text-tertiary">
                  {agent.task}
                </div>
                {agent.persona && (
                  <div className="truncate text-[9px] italic text-ds-text-tertiary">
                    {agent.persona}
                  </div>
                )}
              </div>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

/* --- Helpers --- */

function AgentStatusIcon({
  status,
}: {
  status: AgentDetail["status"];
}) {
  switch (status) {
    case "running":
      return <Loader2 size={12} className="animate-spin text-ds-accent" />;
    case "completed":
      return <CheckCircle2 size={12} className="text-ds-success" />;
    case "error":
      return <AlertCircle size={12} className="text-ds-error" />;
    case "waiting_for_human":
      return <Hand size={12} className="text-ds-warning" />;
    default:
      return <Circle size={12} className="text-ds-text-tertiary" />;
  }
}

/** Fallback: derive agent info from progress logs when API is unavailable */
function deriveAgentsFromLogs(logs: ProgressMessage[]): AgentDetail[] {
  const agentMap = new Map<string, AgentDetail>();
  for (const log of logs) {
    const name = log.task || "agent";
    agentMap.set(name, {
      agent_id: name,
      name,
      persona: "",
      task: log.message,
      status:
        log.status === "completed"
          ? "completed"
          : log.status === "error" || log.status === "failed"
            ? "error"
            : log.status === "running"
              ? "running"
              : "idle",
      modules: [],
      messages: [],
    });
  }
  return Array.from(agentMap.values());
}
