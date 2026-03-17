/** TypeScript interfaces matching backend Pydantic schemas. */

export interface Choice {
  id: string;
  label: string;
  description: string;
  pros: string[];
  cons: string[];
  recommended: boolean;
  reason: string;
}

export type PlanMode = "auto" | "choice";

export interface AutoDecision {
  choice_id: string;
  label: string;
}

// Plan API
export interface PlanStartResponse {
  plan_id: string;
  first_message: string;
  choices: Choice[] | null;
  mode: PlanMode;
  auto_decisions: AutoDecision[] | null;
  plan_document: string | null;
  vibe_files: Record<string, string> | null;
}

export interface PlanRespondResponse {
  message: string;
  choices: Choice[] | null;
}

export interface PlanStatusResponse {
  step: string;
  decisions_count: number;
  complete: boolean;
}

export interface PlanChoicesResponse {
  choices: Choice[];
  topic: string;
}

export interface PlanApproveResponse {
  plan_document: string;
  vibe_files: Record<string, string>;
}

// Execute API
export interface ExecuteStartResponse {
  job_id: string;
}

export interface ExecuteStopResponse {
  status: string;
}

export interface ExecuteStatusResponse {
  phase: number;
  sprint: number;
  progress: number;
  cost: number;
  system_status: string;
  phase_status: string;
  total_phases: number;
  total_iterations: number;
}

// Diff API
export interface DiffFile {
  path: string;
  old_content: string;
  new_content: string;
  status: "added" | "modified" | "deleted";
}

export interface DiffResponse {
  files: DiffFile[];
}

// Preview API
export interface FileTreeNode {
  name: string;
  type: "file" | "directory";
  path: string;
  children: FileTreeNode[] | null;
}

export interface FileContentResponse {
  content: string;
  language: string;
}

export interface TestResult {
  name: string;
  passed: boolean;
  output: string;
}

export interface TestResultResponse {
  total: number;
  passed: number;
  failed: number;
  results: TestResult[];
}

// Vibe Files (Plan markdown documents)
export interface VibeFile {
  name: string;
  path: string;
  content: string;
}

export interface VibeFileListResponse {
  files: VibeFile[];
}

// Agent HITL (Human-in-the-Loop)
export interface AgentMessage {
  role: "agent" | "human";
  content: string;
  timestamp: string;
}

export interface AgentDetail {
  agent_id: string;
  name: string;
  persona: string;
  task: string;
  status: "running" | "completed" | "error" | "idle" | "waiting_for_human";
  modules: string[];
  messages: AgentMessage[];
}

export interface AgentListResponse {
  agents: AgentDetail[];
}

export interface AgentMessageResponse {
  message: string;
}

// Settings API
export type Tier = "low" | "mid" | "high" | "max";

export interface SettingsResponse {
  tier: Tier;
  api_key_configured: boolean;
  max_agents: number;
}

export interface ApiKeyResponse {
  valid: boolean;
  message: string;
}

export interface TierResponse {
  tier: Tier;
  max_agents: number;
}

// WebSocket
export interface ProgressMessage {
  type: string;
  phase: number;
  sprint: number;
  task: string;
  status: string;
  message: string;
  timestamp: string;
}
