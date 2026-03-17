import client from "./client";
import type { SettingsResponse, ApiKeyResponse, TierResponse, Tier } from "./types";

export async function getSettings(): Promise<SettingsResponse> {
  const res = await client.get<SettingsResponse>("/settings");
  return res.data;
}

export async function validateApiKey(key: string): Promise<ApiKeyResponse> {
  const res = await client.post<ApiKeyResponse>("/settings/api-key", { key });
  return res.data;
}

export async function setTier(tier: Tier): Promise<TierResponse> {
  const res = await client.post<TierResponse>("/settings/tier", { tier });
  return res.data;
}
