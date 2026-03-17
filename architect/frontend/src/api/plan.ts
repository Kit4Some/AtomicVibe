import client from "./client";
import type {
  PlanStartResponse,
  PlanRespondResponse,
  PlanStatusResponse,
  PlanChoicesResponse,
  PlanApproveResponse,
  PlanMode,
} from "./types";

export async function startPlan(
  userRequest: string,
  mode: PlanMode = "choice"
): Promise<PlanStartResponse> {
  const { data } = await client.post<PlanStartResponse>("/plan/start", {
    user_request: userRequest,
    mode,
  });
  return data;
}

export async function respondToPlan(
  planId: string,
  message: string,
  choiceId?: string
): Promise<PlanRespondResponse> {
  const { data } = await client.post<PlanRespondResponse>(
    `/plan/${planId}/respond`,
    { message, choice_id: choiceId ?? null }
  );
  return data;
}

export async function getPlanStatus(
  planId: string
): Promise<PlanStatusResponse> {
  const { data } = await client.get<PlanStatusResponse>(
    `/plan/${planId}/status`
  );
  return data;
}

export async function getPlanChoices(
  planId: string
): Promise<PlanChoicesResponse> {
  const { data } = await client.get<PlanChoicesResponse>(
    `/plan/${planId}/choices`
  );
  return data;
}

export async function approvePlan(
  planId: string
): Promise<PlanApproveResponse> {
  const { data } = await client.post<PlanApproveResponse>(
    `/plan/${planId}/approve`
  );
  return data;
}
