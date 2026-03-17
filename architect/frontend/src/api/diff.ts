import client from "./client";
import type { DiffResponse } from "./types";

export async function getDiff(jobId: string): Promise<DiffResponse> {
  const { data } = await client.get<DiffResponse>(`/diff/${jobId}`);
  return data;
}
