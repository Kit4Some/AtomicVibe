import { useState, useRef, useEffect, useCallback } from "react";
import {
  Send,
  FileText,
  X,
  Bot,
  Hand,
  Zap,
  SlidersHorizontal,
} from "lucide-react";
import ChatMessage from "./ChatMessage";
import ChoiceSelector from "./ChoiceSelector";
import ProgressTracker from "./ProgressTracker";
import { startPlan, respondToPlan, approvePlan } from "../api/plan";
import { startExecution, getExecutionStatus } from "../api/execute";
import { getVibeFile } from "../api/vibe";
import { getAgent, sendAgentMessage } from "../api/agents";
import { useWebSocket } from "../hooks/useWebSocket";
import { useAppState, useAppDispatch } from "../context/AppContext";
import type {
  Choice,
  PlanMode,
  ProgressMessage,
  ExecuteStatusResponse,
  VibeFile,
  AgentDetail,
  AgentMessage,
} from "../api/types";

interface Message {
  role: "assistant" | "user";
  content: string;
}

interface ChatPanelProps {
  onStatusChange?: (status: ExecuteStatusResponse | null) => void;
  onRunningChange?: (running: boolean) => void;
  onLogsChange?: (logs: ProgressMessage[]) => void;
  // Plan file context
  selectedVibeFile?: string | null;
  onVibeFileSelected?: (path: string | null) => void;
  // Agent HITL context
  selectedAgent?: string | null;
  onAgentDeselected?: () => void;
}

export default function ChatPanel({
  onStatusChange,
  onRunningChange,
  onLogsChange,
  selectedVibeFile,
  onVibeFileSelected,
  selectedAgent,
  onAgentDeselected,
}: ChatPanelProps) {
  const { planId, jobId } = useAppState();
  const dispatch = useAppDispatch();

  // Plan state
  const [messages, setMessages] = useState<Message[]>([]);
  const [choices, setChoices] = useState<Choice[] | null>(null);
  const [isComplete, setIsComplete] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [input, setInput] = useState("");
  const [started, setStarted] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [planMode, setPlanMode] = useState<PlanMode>("choice");

  // Execute state
  const [status, setStatus] = useState<ExecuteStatusResponse | null>(null);
  const [logs, setLogs] = useState<ProgressMessage[]>([]);
  const [isRunning, setIsRunning] = useState(false);

  // Vibe file context
  const [vibeFile, setVibeFile] = useState<VibeFile | null>(null);

  // Agent HITL context
  const [agentDetail, setAgentDetail] = useState<AgentDetail | null>(null);
  const [agentMessages, setAgentMessages] = useState<AgentMessage[]>([]);

  const chatEndRef = useRef<HTMLDivElement>(null);

  // Determine current context
  const context: "agent" | "file" | "plan" = selectedAgent
    ? "agent"
    : selectedVibeFile
      ? "file"
      : "plan";

  // Forward state up
  useEffect(() => { onStatusChange?.(status); }, [status, onStatusChange]);
  useEffect(() => { onRunningChange?.(isRunning); }, [isRunning, onRunningChange]);
  useEffect(() => { onLogsChange?.(logs); }, [logs, onLogsChange]);

  // Auto-scroll
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, logs, agentMessages]);

  // Fetch vibe file when selected
  useEffect(() => {
    if (!selectedVibeFile || selectedVibeFile === "__new__" || !planId) {
      setVibeFile(null);
      return;
    }
    getVibeFile(planId, selectedVibeFile)
      .then(setVibeFile)
      .catch(() => setVibeFile(null));
  }, [selectedVibeFile, planId]);

  // Fetch agent details when selected
  useEffect(() => {
    if (!selectedAgent || !jobId) {
      setAgentDetail(null);
      setAgentMessages([]);
      return;
    }
    getAgent(jobId, selectedAgent)
      .then((a) => {
        setAgentDetail(a);
        setAgentMessages(a.messages);
      })
      .catch(() => {
        setAgentDetail(null);
        setAgentMessages([]);
      });
  }, [selectedAgent, jobId]);

  // Poll agent messages when agent is selected
  useEffect(() => {
    if (!selectedAgent || !jobId) return;
    const interval = setInterval(() => {
      getAgent(jobId, selectedAgent)
        .then((a) => {
          setAgentDetail(a);
          setAgentMessages(a.messages);
        })
        .catch(() => {});
    }, 3000);
    return () => clearInterval(interval);
  }, [selectedAgent, jobId]);

  // WebSocket for execution progress
  const wsUrl = jobId ? `/ws/progress/${jobId}` : null;

  const handleWsMessage = useCallback((data: string) => {
    try {
      const parsed = JSON.parse(data);
      if (parsed.type === "heartbeat") return;
      const msg = parsed as ProgressMessage;
      setLogs((prev) => [...prev, msg]);
      if (msg.type === "complete" || msg.type === "error") setIsRunning(false);
    } catch {
      // ignore
    }
  }, []);

  useWebSocket(wsUrl, { onMessage: handleWsMessage, reconnect: false });

  // Poll execution status
  useEffect(() => {
    if (!jobId) return;
    getExecutionStatus(jobId).then(setStatus);
    if (!isRunning) return;
    const interval = setInterval(() => {
      getExecutionStatus(jobId).then(setStatus);
    }, 3000);
    return () => clearInterval(interval);
  }, [jobId, isRunning]);

  // --- Plan handlers ---
  const handleStart = async () => {
    if (!input.trim()) return;
    const userMessage = input.trim();
    setInput("");
    setMessages((prev) => [...prev, { role: "user", content: userMessage }]);
    setIsLoading(true);
    setError(null);
    try {
      const res = await startPlan(userMessage, planMode);
      dispatch({ type: "SET_PLAN_ID", payload: res.plan_id });
      setStarted(true);

      if (res.mode === "auto") {
        // Auto mode: show summary of auto-selected decisions, then start execution
        const decisions = res.auto_decisions ?? [];
        const summary = decisions.map((d) => `  [${d.choice_id}] ${d.label}`).join("\n");
        setMessages((prev) => [
          ...prev,
          {
            role: "assistant",
            content:
              `Auto Mode: ${decisions.length} decisions auto-selected (recommended):\n${summary}\n\nGenerating orchestration files and starting execution...`,
          },
        ]);

        // Start execution with vibe_files from auto plan
        if (res.vibe_files) {
          const execRes = await startExecution(res.plan_id, res.vibe_files);
          dispatch({ type: "SET_JOB_ID", payload: execRes.job_id });
          setIsRunning(true);
          setLogs([]);
          setMessages((prev) => [
            ...prev,
            { role: "assistant", content: "Execution started. Agents are working..." },
          ]);
        }
      } else {
        // Choice mode: show first message and choices
        setMessages((prev) => [
          ...prev,
          { role: "assistant", content: res.first_message },
        ]);
        if (res.choices) setChoices(res.choices);
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Failed to start plan session";
      setError(msg);
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: `Error: ${msg}` },
      ]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleSend = async (message: string, choiceId?: string) => {
    if (!planId) return;
    setChoices(null);
    setMessages((prev) => [...prev, { role: "user", content: message }]);
    setIsLoading(true);
    setError(null);
    try {
      const res = await respondToPlan(planId, message, choiceId);
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: res.message },
      ]);
      if (res.choices) {
        setChoices(res.choices);
      } else {
        setIsComplete(true);
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Failed to send message";
      setError(msg);
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: `Error: ${msg}` },
      ]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleChoiceSelect = (id: string) => {
    const choice = choices?.find((c) => c.id === id);
    if (choice) handleSend(`Selected: ${choice.label}`, id);
  };

  const handleApprove = async () => {
    if (!planId) return;
    setIsLoading(true);
    setError(null);
    try {
      const approveRes = await approvePlan(planId);
      const execRes = await startExecution(planId, approveRes.vibe_files);
      dispatch({ type: "SET_JOB_ID", payload: execRes.job_id });
      setIsRunning(true);
      setLogs([]);
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: "Plan approved. Execution started." },
      ]);
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Failed to approve plan";
      setError(msg);
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: `Error: ${msg}` },
      ]);
    } finally {
      setIsLoading(false);
    }
  };

  // --- File edit handler (sends instruction about file to plan chat) ---
  const handleFileEditSend = async () => {
    if (!input.trim() || !planId || !selectedVibeFile) return;
    const fileRef =
      selectedVibeFile === "__new__"
        ? "[Create new document] "
        : `[Edit: ${selectedVibeFile}] `;
    await handleSend(fileRef + input.trim());
    setInput("");
  };

  // --- Agent HITL handler ---
  const handleAgentMessageSend = async () => {
    if (!input.trim() || !jobId || !selectedAgent) return;
    const userMsg = input.trim();
    setInput("");
    setAgentMessages((prev) => [
      ...prev,
      { role: "human", content: userMsg, timestamp: new Date().toISOString() },
    ]);
    try {
      await sendAgentMessage(jobId, selectedAgent, userMsg);
    } catch {
      // optimistic — message already shown
    }
  };

  const handleFormSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim()) return;
    if (context === "agent") {
      await handleAgentMessageSend();
    } else if (context === "file") {
      await handleFileEditSend();
    } else if (!started) {
      await handleStart();
    } else {
      const msg = input.trim();
      setInput("");
      await handleSend(msg);
    }
  };

  return (
    <div className="flex h-full flex-col bg-ds-bg">
      {/* Context header */}
      {context === "agent" && agentDetail && (
        <AgentContextHeader agent={agentDetail} onClose={onAgentDeselected} />
      )}
      {context === "file" && (
        <FileContextHeader
          vibeFile={vibeFile}
          isNew={selectedVibeFile === "__new__"}
          onClose={() => onVibeFileSelected?.(null)}
        />
      )}

      {/* Progress tracker (when executing, in plan context) */}
      {jobId && context === "plan" && (
        <div className="border-b border-ds-border-subtle p-2">
          <ProgressTracker
            phase={status?.phase ?? 1}
            totalPhases={status?.total_phases ?? 4}
            sprint={status?.sprint ?? 0}
            progress={status?.progress ?? 0}
            status={isRunning ? "running" : (status?.system_status ?? "idle")}
          />
        </div>
      )}

      {/* Content area */}
      <div className="flex-1 overflow-y-auto p-3">
        {context === "agent" ? (
          <AgentChatView messages={agentMessages} agent={agentDetail} />
        ) : context === "file" ? (
          <FileEditView vibeFile={vibeFile} isNew={selectedVibeFile === "__new__"} messages={messages} />
        ) : (
          <PlanChatView
            messages={messages}
            logs={logs}
            isLoading={isLoading}
            jobId={jobId}
          />
        )}
        <div ref={chatEndRef} />
      </div>

      {/* Error banner */}
      {error && (
        <div className="mx-3 mb-1 flex items-center gap-2 rounded-[var(--radius-md)] border border-ds-error/30 bg-ds-error/10 px-3 py-2">
          <span className="flex-1 text-[12px] text-ds-error">{error}</span>
          <button
            onClick={() => setError(null)}
            className="flex-shrink-0 text-[11px] text-ds-error/60 hover:text-ds-error"
          >
            <X size={12} />
          </button>
        </div>
      )}

      {/* Mode selector (before plan starts) */}
      {context === "plan" && !started && !jobId && (
        <div className="mx-3 mb-1 flex items-center gap-1">
          <button
            onClick={() => setPlanMode("auto")}
            className={`flex items-center gap-1 rounded-full px-3 py-1 text-[11px] font-medium transition-colors ${
              planMode === "auto"
                ? "bg-ds-accent text-ds-accent-text"
                : "bg-ds-surface text-ds-text-secondary hover:bg-ds-surface-hover"
            }`}
          >
            <Zap size={11} />
            Auto
          </button>
          <button
            onClick={() => setPlanMode("choice")}
            className={`flex items-center gap-1 rounded-full px-3 py-1 text-[11px] font-medium transition-colors ${
              planMode === "choice"
                ? "bg-ds-accent text-ds-accent-text"
                : "bg-ds-surface text-ds-text-secondary hover:bg-ds-surface-hover"
            }`}
          >
            <SlidersHorizontal size={11} />
            Choice
          </button>
          <span className="ml-1 text-[10px] text-ds-text-tertiary">
            {planMode === "auto"
              ? "Recommended choices auto-selected"
              : "You select each decision"}
          </span>
        </div>
      )}

      {/* Input area */}
      <div className="px-3 pb-3 pt-2">
        {context === "plan" && choices && choices.length > 0 ? (
          <ChoiceSelector choices={choices} onSelect={handleChoiceSelect} />
        ) : context === "plan" && isComplete && !jobId ? (
          <button
            onClick={handleApprove}
            disabled={isLoading}
            className="w-full rounded-full bg-ds-success px-4 py-2 text-[13px] font-semibold text-white transition-colors hover:brightness-110 disabled:opacity-50"
          >
            Approve & Start Execution
          </button>
        ) : context === "plan" && jobId ? null : (
          <form onSubmit={handleFormSubmit} className="flex items-center gap-0 rounded-full border border-ds-input-border bg-ds-input-bg pl-4 pr-1">
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder={
                context === "agent"
                  ? "Send message to agent..."
                  : context === "file"
                    ? selectedVibeFile === "__new__"
                      ? "Describe the new document..."
                      : "Describe changes to make..."
                    : started
                      ? "Type your response..."
                      : planMode === "auto"
                        ? "Describe your project (auto mode)..."
                        : "Describe your project..."
              }
              disabled={isLoading}
              className="flex-1 border-none bg-transparent py-2 text-[13px] text-ds-text placeholder-ds-text-tertiary focus:outline-none disabled:opacity-50"
            />
            <button
              type="submit"
              disabled={isLoading || !input.trim()}
              className="flex h-7 w-7 flex-shrink-0 items-center justify-center rounded-full bg-ds-accent text-ds-accent-text transition-colors hover:bg-ds-accent-hover disabled:opacity-30"
            >
              <Send size={13} strokeWidth={2} />
            </button>
          </form>
        )}
      </div>
    </div>
  );
}

/* --- Context Headers --- */

function AgentContextHeader({
  agent,
  onClose,
}: {
  agent: AgentDetail;
  onClose?: () => void;
}) {
  return (
    <div className="flex items-center gap-2 border-b border-ds-border-subtle bg-ds-surface px-3 py-2">
      <Bot size={14} className="flex-shrink-0 text-ds-accent" />
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-1.5">
          <span className="truncate text-[12px] font-medium text-ds-text">
            {agent.name}
          </span>
          {agent.status === "waiting_for_human" && (
            <span className="flex items-center gap-0.5 rounded-full bg-ds-warning-subtle px-1.5 py-px text-[9px] font-bold text-ds-warning">
              <Hand size={8} />
              HITL
            </span>
          )}
        </div>
        <div className="truncate text-[10px] text-ds-text-tertiary">
          {agent.task}
        </div>
      </div>
      <button
        onClick={onClose}
        className="flex h-5 w-5 flex-shrink-0 items-center justify-center rounded-[var(--radius-sm)] text-ds-icon hover:bg-ds-surface-hover hover:text-ds-text"
      >
        <X size={12} />
      </button>
    </div>
  );
}

function FileContextHeader({
  vibeFile,
  isNew,
  onClose,
}: {
  vibeFile: VibeFile | null;
  isNew: boolean;
  onClose?: () => void;
}) {
  return (
    <div className="flex items-center gap-2 border-b border-ds-border-subtle bg-ds-surface px-3 py-2">
      <FileText size={14} className="flex-shrink-0 text-ds-accent" />
      <div className="min-w-0 flex-1">
        <span className="truncate text-[12px] font-medium text-ds-text">
          {isNew ? "New Document" : vibeFile?.name ?? "Loading..."}
        </span>
      </div>
      <button
        onClick={onClose}
        className="flex h-5 w-5 flex-shrink-0 items-center justify-center rounded-[var(--radius-sm)] text-ds-icon hover:bg-ds-surface-hover hover:text-ds-text"
      >
        <X size={12} />
      </button>
    </div>
  );
}

/* --- Content Views --- */

function PlanChatView({
  messages,
  logs,
  isLoading,
  jobId,
}: {
  messages: Message[];
  logs: ProgressMessage[];
  isLoading: boolean;
  jobId: string | null;
}) {
  return (
    <>
      {messages.length === 0 && logs.length === 0 && (
        <div className="flex h-full items-center justify-center">
          <p className="text-[13px] text-ds-text-tertiary">
            Describe your project to begin
          </p>
        </div>
      )}

      {messages.map((msg, i) => (
        <ChatMessage key={`msg-${i}`} role={msg.role} content={msg.content} />
      ))}

      {isLoading && !jobId && (
        <div className="mb-3 flex justify-start">
          <div className="animate-pulse rounded-[var(--radius-lg)] bg-ds-accent-subtle px-4 py-3 text-[13px] text-ds-accent">
            Thinking...
          </div>
        </div>
      )}

      {logs.length > 0 && (
        <div className="mt-2 space-y-0.5 font-mono text-[11px]">
          {logs.map((log, i) => (
            <div
              key={`log-${i}`}
              className={`flex gap-2 rounded-[var(--radius-sm)] px-2 py-0.5 ${
                log.status === "completed"
                  ? "text-ds-success"
                  : log.status === "running"
                    ? "text-ds-accent"
                    : log.status === "error" || log.status === "failed"
                      ? "text-ds-error"
                      : "text-ds-text-tertiary"
              }`}
            >
              <span className="flex-shrink-0 text-ds-text-tertiary">
                {new Date(log.timestamp).toLocaleTimeString()}
              </span>
              <span className="truncate">{log.message}</span>
            </div>
          ))}
        </div>
      )}
    </>
  );
}

function AgentChatView({
  messages,
  agent,
}: {
  messages: AgentMessage[];
  agent: AgentDetail | null;
}) {
  if (!agent) {
    return (
      <div className="flex h-full items-center justify-center">
        <p className="text-[13px] text-ds-text-tertiary">Loading agent...</p>
      </div>
    );
  }

  return (
    <>
      {/* Agent info card */}
      <div className="mb-3 rounded-[var(--radius-md)] border border-ds-border bg-ds-surface p-2.5">
        <div className="mb-1 text-[10px] font-semibold uppercase tracking-wider text-ds-text-tertiary">
          Agent Info
        </div>
        {agent.persona && (
          <div className="mb-1 text-[11px] italic text-ds-text-secondary">
            {agent.persona}
          </div>
        )}
        {agent.modules.length > 0 && (
          <div className="flex flex-wrap gap-1">
            {agent.modules.map((m) => (
              <span
                key={m}
                className="rounded-[var(--radius-sm)] bg-ds-bg-subtle px-1.5 py-px text-[10px] text-ds-text-tertiary"
              >
                {m}
              </span>
            ))}
          </div>
        )}
      </div>

      {/* Messages */}
      {messages.length === 0 ? (
        <div className="flex h-32 items-center justify-center">
          <p className="text-center text-[12px] text-ds-text-tertiary">
            {agent.status === "waiting_for_human"
              ? "Agent is waiting for your input."
              : "No messages yet. Send a message to interact with this agent."}
          </p>
        </div>
      ) : (
        <div className="space-y-2">
          {messages.map((msg, i) => (
            <div
              key={i}
              className={`flex ${msg.role === "human" ? "justify-end" : "justify-start"}`}
            >
              <div
                className={`max-w-[90%] rounded-[var(--radius-lg)] px-3 py-2 text-[12px] ${
                  msg.role === "human"
                    ? "bg-ds-accent text-ds-accent-text"
                    : "bg-ds-surface text-ds-text-secondary"
                }`}
              >
                <div className="whitespace-pre-wrap">{msg.content}</div>
                <div
                  className={`mt-1 text-[9px] ${
                    msg.role === "human"
                      ? "text-ds-accent-text/60"
                      : "text-ds-text-tertiary"
                  }`}
                >
                  {new Date(msg.timestamp).toLocaleTimeString()}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </>
  );
}

function FileEditView({
  vibeFile,
  isNew,
  messages,
}: {
  vibeFile: VibeFile | null;
  isNew: boolean;
  messages: Message[];
}) {
  // Show file content as a preview, then show related chat messages
  return (
    <>
      {isNew ? (
        <div className="mb-3 rounded-[var(--radius-md)] border border-dashed border-ds-border bg-ds-surface p-3 text-center">
          <FileText size={20} className="mx-auto mb-1.5 text-ds-icon" />
          <p className="text-[12px] text-ds-text-secondary">New Document</p>
          <p className="mt-0.5 text-[11px] text-ds-text-tertiary">
            Describe what this document should contain.
          </p>
        </div>
      ) : vibeFile ? (
        <div className="mb-3">
          <div className="mb-1.5 text-[10px] font-semibold uppercase tracking-wider text-ds-text-tertiary">
            {vibeFile.name}
          </div>
          <div className="max-h-[300px] overflow-y-auto rounded-[var(--radius-md)] border border-ds-border bg-ds-surface p-2.5">
            <pre className="whitespace-pre-wrap font-mono text-[11px] leading-relaxed text-ds-text-secondary">
              {vibeFile.content}
            </pre>
          </div>
        </div>
      ) : (
        <div className="flex h-32 items-center justify-center">
          <p className="text-[12px] text-ds-text-tertiary">Loading file...</p>
        </div>
      )}

      {/* Related messages (file edit conversations) */}
      {messages
        .filter((m) => m.content.includes(vibeFile?.name ?? "__impossible__"))
        .map((msg, i) => (
          <ChatMessage key={`file-msg-${i}`} role={msg.role} content={msg.content} />
        ))}

      <p className="mt-2 text-[10px] leading-relaxed text-ds-text-tertiary">
        Use the input below to describe edits, additions, or refinements to
        this document. Your instructions will be sent to the planning assistant.
      </p>
    </>
  );
}
