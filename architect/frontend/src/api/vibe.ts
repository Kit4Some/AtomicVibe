import client from "./client";
import type { VibeFile, VibeFileListResponse } from "./types";

/** List all .vibe/ markdown files for a plan */
export async function listVibeFiles(planId: string): Promise<VibeFile[]> {
  const res = await client.get<VibeFileListResponse>(
    `/plan/${planId}/files`
  );
  return res.data.files;
}

/** Get a single vibe file's content */
export async function getVibeFile(
  planId: string,
  path: string
): Promise<VibeFile> {
  const res = await client.get<VibeFile>(`/plan/${planId}/files/${encodeURIComponent(path)}`);
  return res.data;
}

/** Save (create or update) a vibe file */
export async function saveVibeFile(
  planId: string,
  path: string,
  content: string
): Promise<void> {
  await client.put(`/plan/${planId}/files/${encodeURIComponent(path)}`, {
    content,
  });
}

/** Delete a vibe file */
export async function deleteVibeFile(
  planId: string,
  path: string
): Promise<void> {
  await client.delete(`/plan/${planId}/files/${encodeURIComponent(path)}`);
}
