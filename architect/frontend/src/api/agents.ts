import client from "./client";
import type { AgentDetail, AgentListResponse, AgentMessageResponse } from "./types";

/** List all agents for a running job */
export async function listAgents(jobId: string): Promise<AgentDetail[]> {
  const res = await client.get<AgentListResponse>(
    `/execute/${jobId}/agents`
  );
  return res.data.agents;
}

/** Get a single agent's details including HITL messages */
export async function getAgent(
  jobId: string,
  agentId: string
): Promise<AgentDetail> {
  const res = await client.get<AgentDetail>(
    `/execute/${jobId}/agents/${agentId}`
  );
  return res.data;
}

/** Send a human-in-the-loop message to a specific agent */
export async function sendAgentMessage(
  jobId: string,
  agentId: string,
  message: string
): Promise<AgentMessageResponse> {
  const res = await client.post<AgentMessageResponse>(
    `/execute/${jobId}/agents/${agentId}/message`,
    { message }
  );
  return res.data;
}
