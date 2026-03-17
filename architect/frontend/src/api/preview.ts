import client from "./client";
import type {
  FileTreeNode,
  FileContentResponse,
  TestResultResponse,
} from "./types";

export async function getFileTree(jobId: string): Promise<FileTreeNode> {
  const { data } = await client.get<FileTreeNode>(`/preview/${jobId}/tree`);
  return data;
}

export async function getFileContent(
  jobId: string,
  path: string
): Promise<FileContentResponse> {
  const { data } = await client.get<FileContentResponse>(
    `/preview/${jobId}/file`,
    { params: { path } }
  );
  return data;
}

export async function getTestResults(
  jobId: string
): Promise<TestResultResponse> {
  const { data } = await client.get<TestResultResponse>(
    `/preview/${jobId}/tests`
  );
  return data;
}
