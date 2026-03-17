import client from "./client";
import type {
  ExecuteStartResponse,
  ExecuteStopResponse,
  ExecuteStatusResponse,
} from "./types";

export async function startExecution(
  planId: string,
  vibeFiles?: Record<string, string>
): Promise<ExecuteStartResponse> {
  const { data } = await client.post<ExecuteStartResponse>("/execute/start", {
    plan_id: planId,
    vibe_files: vibeFiles,
  });
  return data;
}

export async function stopExecution(
  jobId: string
): Promise<ExecuteStopResponse> {
  const { data } = await client.post<ExecuteStopResponse>(
    `/execute/${jobId}/stop`
  );
  return data;
}

export async function getExecutionStatus(
  jobId: string
): Promise<ExecuteStatusResponse> {
  const { data } = await client.get<ExecuteStatusResponse>(
    `/execute/${jobId}/status`
  );
  return data;
}
